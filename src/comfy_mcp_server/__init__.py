from mcp.server.fastmcp import FastMCP, Image, Context
import json
import time
import os
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

prompt_template = json.load(
    open(workflow, "r")
) if workflow is not None else None

# Backwards compatibility: PROMPT_NODE_ID takes precedence
prompt_node_id = os.environ.get("PROMPT_NODE_ID")
pos_prompt_node_id = os.environ.get("POS_PROMPT_NODE_ID")
neg_prompt_node_id = os.environ.get("NEG_PROMPT_NODE_ID")

# Apply backwards compatibility logic
if prompt_node_id is not None:
    # Legacy parameter present - use it for positive
    pos_prompt_node_id = prompt_node_id
elif pos_prompt_node_id is not None:
    # New parameter present without legacy - copy to legacy variable
    prompt_node_id = pos_prompt_node_id
else:
    # Neither present
    prompt_node_id = None
    pos_prompt_node_id = None

output_node_id = os.environ.get("OUTPUT_NODE_ID")
output_mode = os.environ.get("OUTPUT_MODE")

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
    ctx: Context = None
):
    """Generate an image using ComfyUI workflow

    Args:
        positive_prompt: The positive prompt describing what to generate
        negative_prompt: The negative prompt describing what to avoid (optional)
        ctx: MCP context for logging
    """
    # Set positive prompt
    if pos_prompt_node_id in prompt_template:
        prompt_template[pos_prompt_node_id]['inputs']['text'] = positive_prompt
    else:
        return f"Error: Positive prompt node ID '{pos_prompt_node_id}' not found in workflow template"

    # Set negative prompt if node is configured and exists in template
    if neg_prompt_node_id is not None and negative_prompt:
        if neg_prompt_node_id in prompt_template:
            prompt_template[neg_prompt_node_id]['inputs']['text'] = negative_prompt
        else:
            ctx.info(f"Warning: Negative prompt node ID '{neg_prompt_node_id}' not found in workflow, skipping negative prompt")

    payload = {"prompt": prompt_template}
    data = json.dumps(payload).encode('utf-8')
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
                    status = history_resp_data[prompt_id]['status']['completed']

                    if status:
                        output_data = (
                            history_resp_data[prompt_id]['outputs'][output_node_id]['images'][0]
                        )
                        url_values = urllib.parse.urlencode(output_data)
                        file_url = get_file_url(host, url_values)
                        override_file_url = get_file_url(override_host, url_values)

                        file_req = urllib.request.Request(file_url)
                        file_resp = urllib.request.urlopen(file_req)

                        if file_resp.status == 200:
                            ctx.info("Image generated")
                            output_file = file_resp.read()
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


def run_server():
    errors = []
    if host is None:
        errors.append("- COMFY_URL environment variable not set")
    if workflow is None:
        errors.append("- COMFY_WORKFLOW_JSON_FILE environment variable not set")
    if pos_prompt_node_id is None:
        errors.append(
            "- Either PROMPT_NODE_ID or POS_PROMPT_NODE_ID environment variable must be set"
        )
    if output_node_id is None:
        errors.append("- OUTPUT_NODE_ID environment variable not set")

    if errors:
        errors = ["Failed to start Comfy MCP Server:"] + errors
        return "\n".join(errors)
    else:
        mcp.run()


if __name__ == "__main__":
    run_server()
