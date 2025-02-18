from mcp.server.fastmcp import FastMCP, Image, Context
import json
import urllib
from urllib import request
import time
import os

mcp = FastMCP("Comfy MCP Server")

host = os.environ.get("COMFY_URL")
override_host = os.environ.get("COMFY_URL_EXTERNAL")
if override_host is None:
    override_host = host
workflow = os.environ.get("COMFY_WORKFLOW_JSON_FILE")

prompt_template = json.load(
    open(workflow, "r")
) if workflow is not None else None

prompt_node_id = os.environ.get("PROMPT_NODE_ID")
output_node_id = os.environ.get("OUTPUT_NODE_ID")
output_mode = os.environ.get("OUTPUT_MODE")


def get_file_url(server: str, url_values: str) -> str:
    return f"{server}/view?{url_values}"


@mcp.tool()
def generate_image(prompt: str, ctx: Context) -> Image | str:
    """Generate an image using ComfyUI workflow"""

    prompt_template[prompt_node_id]['inputs']['text'] = prompt
    p = {"prompt": prompt_template}
    data = json.dumps(p).encode('utf-8')
    req = request.Request(f"{host}/prompt", data)
    resp = request.urlopen(req)
    response_ready = False
    if resp.status == 200:
        ctx.info("Submitted prompt")
        resp_data = json.loads(resp.read())
        prompt_id = resp_data["prompt_id"]

        for t in range(0, 20):
            history_req = request.Request(
                f"{host}/history/{prompt_id}")
            history_resp = request.urlopen(history_req)
            if history_resp.status == 200:
                ctx.info("Checking status...")
                history_resp_data = json.loads(history_resp.read())
                if prompt_id in history_resp_data:
                    status = (
                        history_resp_data[prompt_id]['status']['completed']
                    )
                    if status:
                        output_data = (
                            history_resp_data[prompt_id]
                            ['outputs'][output_node_id]['images'][0]
                        )
                        url_values = urllib.parse.urlencode(output_data)
                        file_url = get_file_url(host, url_values)
                        override_file_url = get_file_url(
                            override_host, url_values)
                        file_req = request.Request(file_url)
                        file_resp = request.urlopen(file_req)
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
        errors.append(
            "- COMFY_WORKFLOW_JSON_FILE environment variable not set")
    if prompt_node_id is None:
        errors.append("- PROMPT_NODE_ID environment variable not set")
    if output_node_id is None:
        errors.append("- OUTPUT_NODE_ID environment variable not set")

    if len(errors) > 0:
        errors = ["Failed to start Comfy MCP Server:"] + errors
        return "\n".join(errors)
    else:
        mcp.run()


if __name__ == "__main__":
    run_server()
