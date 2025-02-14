from mcp.server.fastmcp import FastMCP, Image, Context
import json
import urllib
from urllib import request
import time
import os

mcp = FastMCP("Comfy MCP Server")

host = os.environ.get("COMFY_URL")
mcp_dir = os.path.dirname(__file__)
prompt_template = json.load(
    open(f"{mcp_dir}/Flux-Dev-ComfyUI-Workflow.json", "r")
)


@mcp.tool()
def generate_image(prompt: str, ctx: Context) -> Image | str:
    """Generate an image using Flux dev workflow on Comfy"""

    if host is None:
        return "COMFY_URL environment variable not set"

    prompt_template['6']['inputs']['text'] = prompt
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
                            ['outputs']['9']['images'][0]
                        )
                        url_values = urllib.parse.urlencode(output_data)
                        file_req = request.Request(
                            f"{host}/view?{url_values}")
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
        return Image(data=output_file, format="png")
    else:
        return "Failed to generate image. Please check server logs."


if __name__ == "__main__":
    mcp.run()
