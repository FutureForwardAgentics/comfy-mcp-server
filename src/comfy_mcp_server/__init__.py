"""Comfy MCP Server - Main module for image generation tools."""

import os
import sys
from typing import Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_ollama.chat_models import ChatOllama
from mcp.server.fastmcp import Context, FastMCP

from .comfy_client import ComfyClient
from .config import get_config
from .workflow import WorkflowManager, print_workflow_nodes as _print_workflow_nodes

# Constants
DEFAULT_IMG_SUBDIR = "img"
DEFAULT_SAVE_PATH = "./img"
PROMPT_GENERATION_TEMPLATE = """You are an AI Image Generation Prompt Assistant.
Your job is to review the topic provided by the user for an image generation task and create
an appropriate prompt from it. Respond with a single prompt. Don't ask for feedback about the prompt.

Topic: {topic}
Prompt: """

mcp = FastMCP("Comfy MCP Server")

# Load configuration
cfg = get_config()
host = cfg.comfy_url
override_host = cfg.comfy_url_external

# Initialize ComfyUI client
comfy_client = ComfyClient(
    comfy_url=cfg.comfy_url,
    comfy_url_external=cfg.comfy_url_external,
    comfy_output_dir=cfg.comfy_output_dir,
)

# Load workflow
workflow_manager = WorkflowManager(cfg.workflow_path)
workflow_data = workflow_manager.workflow_data
nodes_lookup = workflow_manager.nodes_lookup
api_workflow = workflow_manager.api_workflow
prompt_template = api_workflow  # For use in generate_image

# Discover nodes
pos_prompt_node_id, neg_prompt_node_id, filepath_node_id, output_node_id, latent_image_node_id = (
    workflow_manager.discover_nodes(
        pos_prompt_override=cfg.pos_prompt_node_id,
        neg_prompt_override=cfg.neg_prompt_node_id,
        filepath_override=cfg.filepath_node_id,
        output_override=cfg.output_node_id,
        latent_image_override=cfg.latent_image_node_id,
    )
)

output_mode = cfg.output_mode
working_dir = cfg.working_dir
ollama_api_base = cfg.ollama_api_base
prompt_llm = cfg.prompt_llm


if cfg.has_ollama_config():

    @mcp.tool()
    def generate_prompt(topic: str, ctx: Context) -> str:
        """Generate an image generation prompt from a topic.

        Args:
            topic: The topic to generate a prompt for
            ctx: MCP context for logging

        Returns:
            Generated image prompt
        """
        model = ChatOllama(base_url=cfg.ollama_api_base, model=cfg.prompt_llm)
        prompt = PromptTemplate.from_template(PROMPT_GENERATION_TEMPLATE)
        chain = prompt | model | StrOutputParser()
        response = chain.invoke({"topic": topic})
        return response


@mcp.tool()
def generate_image(
    positive_prompt: str,
    negative_prompt: str = "",
    save_path: str | None = None,
    width: int | None = None,
    height: int | None = None,
    ctx: Context | None = None,
) -> str:
    """Generate an image using ComfyUI workflow.

    Args:
        positive_prompt: The positive prompt describing what to generate
        negative_prompt: The negative prompt describing what to avoid (optional)
        save_path: Absolute path to directory where images should be saved locally
        width: Width of the generated image in pixels (optional)
        height: Height of the generated image in pixels (optional)
        ctx: MCP context for logging

    Returns:
        Full path to the generated image file
    """
    # Set default save path
    if save_path is None:
        if working_dir:
            save_path = os.path.join(working_dir, DEFAULT_IMG_SUBDIR)
        else:
            save_path = DEFAULT_SAVE_PATH

    # Normalize path to handle trailing slashes
    save_path = os.path.normpath(save_path)

    # Set positive prompt
    if pos_prompt_node_id in prompt_template:
        prompt_template[pos_prompt_node_id]["inputs"]["text"] = positive_prompt
    else:
        return f"Error: Positive prompt node ID '{pos_prompt_node_id}' not found in workflow template"

    # Set negative prompt if node is configured and exists in template
    if neg_prompt_node_id is not None and negative_prompt:
        if neg_prompt_node_id in prompt_template:
            prompt_template[neg_prompt_node_id]["inputs"]["text"] = negative_prompt
        else:
            if ctx:
                ctx.info(
                    f"Warning: Negative prompt node ID '{neg_prompt_node_id}' not found in workflow, skipping negative prompt"
                )

    # Set filepath if node is configured
    if filepath_node_id is not None:
        if filepath_node_id in prompt_template:
            prompt_template[filepath_node_id]["inputs"]["text"] = save_path
        else:
            if ctx:
                ctx.info(
                    f"Warning: Filepath node ID '{filepath_node_id}' not found in workflow, skipping save path"
                )

    # Set width and height if provided and node is configured
    if latent_image_node_id is not None:
        if latent_image_node_id in prompt_template:
            if width is not None:
                prompt_template[latent_image_node_id]["inputs"]["width"] = width
            if height is not None:
                prompt_template[latent_image_node_id]["inputs"]["height"] = height
        else:
            if ctx and (width is not None or height is not None):
                ctx.info(
                    f"Warning: Latent image node ID '{latent_image_node_id}' not found in workflow, skipping dimensions"
                )

    # Submit workflow to ComfyUI
    prompt_id = comfy_client.submit_workflow(prompt_template, ctx)
    if not prompt_id:
        return "Error: Failed to submit workflow to ComfyUI"

    # Poll for completion
    result = comfy_client.poll_for_completion(prompt_id, ctx)
    if not result:
        return "Failed to generate image. Please check server logs."

    # Extract output data (not used directly, but validate structure)
    try:
        output_data = result["outputs"][output_node_id]["images"][0]
    except (KeyError, IndexError) as e:
        return f"Error: Invalid output structure from ComfyUI: {e}"

    # Download from ComfyUI and save to local path
    try:
        output_node_config = prompt_template[output_node_id]
        image_bytes, full_path = comfy_client.download_and_save_image(
            output_node_config, prompt_template, save_path, ctx
        )
    except (ValueError, RuntimeError) as e:
        return f"Error downloading/saving image: {e}"
    except Exception as e:
        return f"Unexpected error during image save: {type(e).__name__}: {e}"

    # Return the local file path
    return full_path


def print_schema() -> None:
    """Print the tool schemas for inspection."""
    print("Comfy MCP Server - Available Tools\n")
    print("=" * 80)

    for tool in mcp._tool_manager._tools.values():
        print(f"\nTool: {tool.name}")
        print(f"Description: {tool.description}")
        print("\nParameters:")

        # Get parameters from the tool schema
        properties = tool.parameters.get("properties", {})
        required = tool.parameters.get("required", [])

        for param_name, param_info in properties.items():
            # Handle union types (anyOf)
            if "anyOf" in param_info:
                types = [t.get("type", "unknown") for t in param_info["anyOf"]]
                param_type = " | ".join(types)
            else:
                param_type = param_info.get("type", "any")

            is_required = param_name in required
            default = param_info.get("default")

            if is_required:
                status = " (required)"
            elif "default" in param_info:
                status = f" = {repr(default)}"
            else:
                status = " (optional)"

            print(f"  • {param_name}: {param_type}{status}")

        print("\n" + "-" * 80)


def run_server() -> Optional[str]:
    """Start the MCP server.

    Returns:
        Error message string if startup fails, None otherwise
    """
    # Validate configuration
    errors = cfg.validate_required()

    # Validate node discovery
    if pos_prompt_node_id is None:
        errors.append(
            "- Could not auto-discover positive prompt node. Set POS_PROMPT_NODE_ID environment variable."
        )
    if output_node_id is None:
        errors.append(
            "- Could not auto-discover output node. Set OUTPUT_NODE_ID environment variable."
        )

    if errors:
        errors = ["Failed to start Comfy MCP Server:"] + errors
        if prompt_template is not None:
            errors.append("\nRun with --nodes to see available nodes in your workflow")
        return "\n".join(errors)

    # Log discovered nodes when running in debug mode
    if os.environ.get("DEBUG"):
        print("Auto-discovered nodes:")
        print(f"  Positive prompt: {pos_prompt_node_id}")
        print(f"  Negative prompt: {neg_prompt_node_id or 'None'}")
        print(f"  Output: {output_node_id}")

    mcp.run()
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--schema":
            print_schema()
        elif sys.argv[1] == "--nodes":
            _print_workflow_nodes(workflow_data, cfg.workflow_path)
        elif sys.argv[1] == "--help":
            print("Comfy MCP Server\n")
            print("Usage:")
            print("  comfy-mcp-server           Run the MCP server")
            print("  comfy-mcp-server --schema  Show available tools and parameters")
            print("  comfy-mcp-server --nodes   Show workflow nodes and their IDs")
            print("  comfy-mcp-server --help    Show this help message")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        run_server()
