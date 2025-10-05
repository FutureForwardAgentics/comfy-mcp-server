from mcp.server.fastmcp import FastMCP, Image, Context
import json
import time
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from langchain_ollama.chat_models import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

mcp = FastMCP("Comfy MCP Server")

host = os.environ.get("COMFY_URL")
override_host = os.environ.get("COMFY_URL_EXTERNAL")
if override_host is None:
    override_host = host
workflow = os.environ.get("COMFY_WORKFLOW_JSON_FILE")


def workflow_to_api_format(workflow_data: dict) -> dict:
    """Convert workflow JSON to ComfyUI API prompt format

    Converts from frontend format (with nodes array) to API format (dict of node_id -> node config)
    """
    if "nodes" not in workflow_data:
        return workflow_data  # Already in API format

    api_format = {}
    for node in workflow_data["nodes"]:
        node_id = str(node["id"])
        inputs = {}

        # Map widget values to input names
        if "widgets_values" in node:
            # Find widget inputs
            widget_idx = 0
            for inp in node.get("inputs", []):
                if "widget" in inp:
                    # Widget input - use value from widgets_values
                    if widget_idx < len(node["widgets_values"]):
                        inputs[inp["name"]] = node["widgets_values"][widget_idx]
                        widget_idx += 1
                elif inp.get("link") is not None:
                    # Linked input - reference another node's output
                    # Find the link to get source info
                    for link in workflow_data.get("links", []):
                        if link[0] == inp["link"]:
                            source_node_id = str(link[1])
                            source_output_idx = link[2]
                            inputs[inp["name"]] = [source_node_id, source_output_idx]
                            break

        api_format[node_id] = {"class_type": node["type"], "inputs": inputs}

    return api_format


workflow_data, nodes_lookup = None, None
api_workflow = None

if workflow is not None:
    with open(workflow, "r") as f:
        workflow_data = json.load(f)

    # Create lookup dict for node access
    if "nodes" in workflow_data:
        nodes_lookup = {}
        for node in workflow_data["nodes"]:
            node_id = str(node["id"])
            nodes_lookup[node_id] = node

    # Convert to API format for submission
    api_workflow = workflow_to_api_format(workflow_data)

prompt_template = api_workflow  # For use in generate_image


def auto_discover_node_id(
    workflow_data: dict, title_keywords: list[str], class_type: str = None
) -> str | None:
    """Automatically discover a node ID by searching for keywords in title AND matching class_type"""
    if workflow_data is None:
        return None

    # Extract nodes array from workflow structure
    nodes = workflow_data.get("nodes", [])

    # First pass: Look for nodes with matching title keywords AND class_type
    for node in nodes:
        node_id = str(node.get("id"))
        title = node.get("title", "").lower()
        node_class = node.get("type", "")

        # If both title keyword and class_type match, this is our node
        if title and any(keyword.lower() in title for keyword in title_keywords):
            if class_type is None or node_class == class_type:
                return node_id

    # Second pass: If no title match, fall back to just class_type
    if class_type:
        for node in nodes:
            node_id = str(node.get("id"))
            node_class = node.get("type", "")
            if node_class == class_type:
                return node_id

    return None


# Try to auto-discover node IDs first, then fall back to environment variables
pos_prompt_node_id = auto_discover_node_id(
    workflow_data, ["positive"], "CLIPTextEncode"
)
neg_prompt_node_id = auto_discover_node_id(
    workflow_data, ["negative"], "CLIPTextEncode"
)
output_node_id = auto_discover_node_id(
    workflow_data, ["save", "saveimage"], "SaveImage"
)

# Override with environment variables if provided
# Backwards compatibility: PROMPT_NODE_ID takes precedence
prompt_node_id = os.environ.get("PROMPT_NODE_ID")
if prompt_node_id is not None:
    pos_prompt_node_id = prompt_node_id
elif os.environ.get("POS_PROMPT_NODE_ID") is not None:
    pos_prompt_node_id = os.environ.get("POS_PROMPT_NODE_ID")
    prompt_node_id = pos_prompt_node_id

if os.environ.get("NEG_PROMPT_NODE_ID") is not None:
    neg_prompt_node_id = os.environ.get("NEG_PROMPT_NODE_ID")

if os.environ.get("OUTPUT_NODE_ID") is not None:
    output_node_id = os.environ.get("OUTPUT_NODE_ID")
output_mode = os.environ.get("OUTPUT_MODE")
working_dir = os.environ.get("COMFY_WORKING_DIR")

ollama_api_base = os.environ.get("OLLAMA_API_BASE")
prompt_llm = os.environ.get("PROMPT_LLM")


def get_file_url(server: str, url_values: str) -> str:
    """Construct ComfyUI file view URL from server and URL-encoded parameters"""
    return f"{server}/view?{url_values}"


def submit_workflow(workflow: dict, ctx: Context) -> str:
    """Submit workflow to ComfyUI and return prompt_id"""
    payload = {"prompt": workflow}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{host}/prompt", data)
    resp = urllib.request.urlopen(req)

    if resp.status != 200:
        return None

    if ctx:
        ctx.info("Submitted prompt")
    resp_data = json.loads(resp.read())
    return resp_data.get("prompt_id")


def poll_for_completion(
    prompt_id: str, ctx: Context, max_attempts: int = 20
) -> dict | None:
    """Poll ComfyUI history API until workflow completes or times out"""
    for _ in range(max_attempts):
        history_req = urllib.request.Request(f"{host}/history/{prompt_id}")
        history_resp = urllib.request.urlopen(history_req)

        if history_resp.status == 200:
            if ctx:
                ctx.info("Checking status...")
            history_data = json.loads(history_resp.read())

            if prompt_id in history_data:
                if history_data[prompt_id]["status"]["completed"]:
                    return history_data[prompt_id]

        time.sleep(30)

    return None


def find_latest_image_in_comfy_output(output_node_config: dict) -> str:
    """Find the latest image file from ComfyUI output directory based on SaveImage node config

    Args:
        output_node_config: The SaveImage node configuration from the workflow

    Returns:
        Full path to the most recently created image file
    """
    base_output_dir = "/Volumes/Sidecar/GenAI/ComfyUI/output"

    # Extract filename_prefix from SaveImage node to determine subdirectory
    # Example: "chroma-radiance/image" means search in chroma-radiance subdirectory
    filename_prefix = output_node_config.get("inputs", {}).get("filename_prefix", "")

    # Parse the filename_prefix to extract directory path (before the last /)
    if "/" in filename_prefix:
        prefix_parts = filename_prefix.split("/")
        # Remove the actual filename part (last element)
        dir_parts = prefix_parts[:-1]
        search_dir = os.path.join(base_output_dir, *dir_parts)
    else:
        # No subdirectories, just search base output directory
        search_dir = base_output_dir

    # Find image files in the determined directory
    if not os.path.exists(search_dir):
        raise ValueError(f"ComfyUI output directory not found: {search_dir}")

    image_files = [
        os.path.join(search_dir, f)
        for f in os.listdir(search_dir)
        if os.path.isfile(os.path.join(search_dir, f))
        and f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ]

    if not image_files:
        raise ValueError(f"No image files found in {search_dir}")

    # Sort by creation time (most recent first)
    image_files.sort(key=lambda f: os.path.getctime(f), reverse=True)
    return image_files[0]


def download_and_save_image(
    output_data: dict, save_path: str, ctx: Context
) -> tuple[bytes, str]:
    """Download generated image from ComfyUI and save to local disk

    Args:
        output_data: Output data from ComfyUI history API containing filename and metadata
        save_path: Absolute path to directory where image should be saved locally
        ctx: MCP context for logging

    Returns:
        tuple: (image_bytes, full_path) where full_path is the local saved file path
    """
    # Get the SaveImage node configuration to determine output location
    if output_node_id not in prompt_template:
        raise ValueError(f"SaveImage node {output_node_id} not found in workflow")

    output_node_config = prompt_template[output_node_id]

    # Find the most recently created image file based on SaveImage config
    source_path = find_latest_image_in_comfy_output(output_node_config)
    if ctx:
        ctx.info(f"Found latest image: {os.path.basename(source_path)}")

    # Read the image
    with open(source_path, "rb") as f:
        image_bytes = f.read()

    # Save to local disk with datetime-formatted filename
    os.makedirs(save_path, exist_ok=True)

    # Get file extension from source file
    _, ext = os.path.splitext(source_path)

    # Format: YYYY-mm-dd_HHMMSS.ext
    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    new_filename = f"{timestamp_str}{ext}"
    full_path = os.path.join(save_path, new_filename)

    with open(full_path, "wb") as f:
        f.write(image_bytes)
    if ctx:
        ctx.info(f"Image saved locally to {full_path}")

    return image_bytes, full_path


if ollama_api_base is not None and prompt_llm is not None:

    @mcp.tool()
    def generate_prompt(topic: str, ctx: Context) -> str:
        """Write an image generation prompt for a provided topic"""
        model = ChatOllama(base_url=ollama_api_base, model=prompt_llm)
        prompt = PromptTemplate.from_template(
            """You are an AI Image Generation Prompt Assistant.
Your job is to review the topic provided by the user for an image generation task and create
an appropriate prompt from it. Respond with a single prompt. Don't ask for feedback about the prompt.

Topic: {topic}
Prompt: """
        )
        chain = prompt | model | StrOutputParser()
        response = chain.invoke({"topic": topic})
        return response


@mcp.tool()
def generate_image(
    positive_prompt: str,
    negative_prompt: str = "",
    save_path: str | None = None,
    ctx: Context = None,
):
    """Generate an image using ComfyUI workflow

    Args:
        positive_prompt: The positive prompt describing what to generate
        negative_prompt: The negative prompt describing what to avoid (optional)
        save_path: Absolute path to directory where images should be saved locally (default: {COMFY_WORKING_DIR}/img/ or ./img/)
        ctx: MCP context for logging
    """
    # Set default save path - use absolute path
    if save_path is None:
        if working_dir:
            save_path = os.path.join(working_dir, "img")
        else:
            save_path = "./img"

    # Normalize path to handle trailing slashes
    save_path = os.path.normpath(save_path)

    # Debug logging
    import sys

    print(f"DEBUG: save_path={save_path}", file=sys.stderr)

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

    # Submit workflow to ComfyUI (SaveImage will use its default output directory)
    prompt_id = submit_workflow(prompt_template, ctx)
    if not prompt_id:
        return "Error: Failed to submit workflow to ComfyUI"

    # Poll for completion
    result = poll_for_completion(prompt_id, ctx)
    if not result:
        return "Failed to generate image. Please check server logs."

    # Extract output data
    try:
        output_data = result["outputs"][output_node_id]["images"][0]
    except (KeyError, IndexError) as e:
        return f"Error: Invalid output structure from ComfyUI: {e}"

    # Download from ComfyUI and save to local path
    try:
        image_bytes, full_path = download_and_save_image(output_data, save_path, ctx)
    except (ValueError, RuntimeError) as e:
        return f"Error downloading/saving image: {e}"
    except Exception as e:
        return f"Unexpected error during image save: {type(e).__name__}: {e}"

    # Return result based on output mode
    if output_mode is not None and output_mode.lower() == "url":
        url_values = urllib.parse.urlencode(output_data)
        return get_file_url(override_host, url_values)

    return Image(data=image_bytes, format="png")


def find_nodes_by_title(title: str, wf_data: dict) -> list[str]:
    """Find node IDs by their title"""
    if "nodes" not in wf_data:
        return []
    return [str(node["id"]) for node in wf_data["nodes"] if node.get("title") == title]


def find_nodes_by_class(class_type: str, wf_data: dict) -> list[str]:
    """Find node IDs by their class_type"""
    if "nodes" not in wf_data:
        return []
    return [
        str(node["id"]) for node in wf_data["nodes"] if node.get("type") == class_type
    ]


def print_workflow_nodes():
    """Print all nodes in the workflow with their IDs, titles, and class types"""
    if workflow_data is None:
        print("Error: COMFY_WORKFLOW_JSON_FILE not set or file not found")
        return

    print("Workflow Nodes\n")
    print("=" * 80)
    print(f"Workflow: {workflow}\n")

    nodes = workflow_data.get("nodes", [])
    for node in nodes:
        node_id = node.get("id")
        class_type = node.get("type", "Unknown")
        title = node.get("title", "")

        title_str = f' ("{title}")' if title else ""
        print(f"  [{node_id}] {class_type}{title_str}")

    print("\n" + "-" * 80)
    print("\nCommon node types to look for:")
    print("  • Positive prompt: CLIPTextEncode with title 'Positive'")
    print("  • Negative prompt: CLIPTextEncode with title 'Negative'")
    print("  • Output: SaveImage")
    print("\n" + "=" * 80)


def print_schema():
    """Print the tool schemas for inspection"""
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


def run_server():
    errors = []
    if host is None:
        errors.append("- COMFY_URL environment variable not set")
    if workflow is None:
        errors.append("- COMFY_WORKFLOW_JSON_FILE environment variable not set")
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
    else:
        # Log discovered nodes when running in debug mode
        if os.environ.get("DEBUG"):
            print(f"Auto-discovered nodes:")
            print(f"  Positive prompt: {pos_prompt_node_id}")
            print(f"  Negative prompt: {neg_prompt_node_id or 'None'}")
            print(f"  Output: {output_node_id}")
        mcp.run()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--schema":
            print_schema()
        elif sys.argv[1] == "--nodes":
            print_workflow_nodes()
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
