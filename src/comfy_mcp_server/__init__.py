from mcp.server.fastmcp import FastMCP, Image, Context
import json
import time
import os
import sys
import urllib.parse
import urllib.request
from langchain_ollama.chat_models import ChatOllama
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

mcp = FastMCP("Comfy MCP Server")

host = os.environ.get("COMFY_URL")
override_host = os.environ.get("COMFY_URL_EXTERNAL")
if override_host is None:
    override_host = host
workflow = os.environ.get("COMFY_WORKFLOW_JSON_FILE")

prompt_template = json.load(open(workflow, "r")) if workflow is not None else None


def auto_discover_node_id(
    workflow_data: dict, title_keywords: list[str], class_type: str = None
) -> str | None:
    """Automatically discover a node ID by searching for keywords in title AND matching class_type"""
    if workflow_data is None:
        return None

    # First pass: Look for nodes with matching title keywords AND class_type
    for node_id, node in workflow_data.items():
        title = node.get("_meta", {}).get("title", "").lower()
        node_class = node.get("class_type", "")

        # If both title keyword and class_type match, this is our node
        if title and any(keyword.lower() in title for keyword in title_keywords):
            if class_type is None or node_class == class_type:
                return node_id

    # Second pass: If no title match, fall back to just class_type
    if class_type:
        for node_id, node in workflow_data.items():
            if node.get("class_type") == class_type:
                return node_id

    return None


# Try to auto-discover node IDs first, then fall back to environment variables
pos_prompt_node_id = auto_discover_node_id(
    prompt_template, ["positive"], "CLIPTextEncode"
)
neg_prompt_node_id = auto_discover_node_id(
    prompt_template, ["negative"], "CLIPTextEncode"
)
output_node_id = auto_discover_node_id(
    prompt_template, ["save", "saveimage"], "SaveImage"
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
    return f"{server}/view?{url_values}"


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
        save_path: Directory to save generated images (default: {COMFY_WORKING_DIR}/img/ or ./img/)
        ctx: MCP context for logging
    """
    # Set default save path based on working directory
    if save_path is None:
        if working_dir:
            save_path = os.path.join(working_dir, "img")
        else:
            save_path = "./img"

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
            ctx.info(
                f"Warning: Negative prompt node ID '{neg_prompt_node_id}' not found in workflow, skipping negative prompt"
            )

    payload = {"prompt": prompt_template}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{host}/prompt", data)
    resp = urllib.request.urlopen(req)

    response_ready = False
    if resp.status == 200:
        ctx.info("Submitted prompt")
        resp_data = json.loads(resp.read())
        prompt_id = resp_data["prompt_id"]

        for _ in range(20):
            history_req = urllib.request.Request(f"{host}/history/{prompt_id}")
            history_resp = urllib.request.urlopen(history_req)

            if history_resp.status == 200:
                ctx.info("Checking status...")
                history_resp_data = json.loads(history_resp.read())

                if prompt_id in history_resp_data:
                    status = history_resp_data[prompt_id]["status"]["completed"]

                    if status:
                        output_data = history_resp_data[prompt_id]["outputs"][
                            output_node_id
                        ]["images"][0]
                        url_values = urllib.parse.urlencode(output_data)
                        file_url = get_file_url(host, url_values)
                        override_file_url = get_file_url(override_host, url_values)

                        file_req = urllib.request.Request(file_url)
                        file_resp = urllib.request.urlopen(file_req)

                        if file_resp.status == 200:
                            ctx.info("Image generated")
                            output_file = file_resp.read()

                            # Save image to disk
                            os.makedirs(save_path, exist_ok=True)
                            filename = f"{prompt_id}.png"
                            full_path = os.path.join(save_path, filename)
                            with open(full_path, "wb") as f:
                                f.write(output_file)
                            ctx.info(f"Image saved to {full_path}")

                            response_ready = True
                            break
                    else:
                        time.sleep(1)
                else:
                    time.sleep(1)

    if response_ready:
        if output_mode is not None and output_mode.lower() == "url":
            return override_file_url
        return Image(data=output_file, format="png")
    else:
        return "Failed to generate image. Please check server logs."


def find_nodes_by_title(title: str, workflow_data: dict) -> list[str]:
    """Find node IDs by their title in _meta"""
    return [
        node_id
        for node_id, node in workflow_data.items()
        if node.get("_meta", {}).get("title") == title
    ]


def find_nodes_by_class(class_type: str, workflow_data: dict) -> list[str]:
    """Find node IDs by their class_type"""
    return [
        node_id
        for node_id, node in workflow_data.items()
        if node.get("class_type") == class_type
    ]


def print_workflow_nodes():
    """Print all nodes in the workflow with their IDs, titles, and class types"""
    if prompt_template is None:
        print("Error: COMFY_WORKFLOW_JSON_FILE not set or file not found")
        return

    print("Workflow Nodes\n")
    print("=" * 80)
    print(f"Workflow: {workflow}\n")

    for node_id, node in prompt_template.items():
        class_type = node.get("class_type", "Unknown")
        title = node.get("_meta", {}).get("title", "")

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
