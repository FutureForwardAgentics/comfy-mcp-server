# Comfy MCP Server

[![smithery badge](https://smithery.ai/badge/@lalanikarim/comfy-mcp-server)](https://smithery.ai/server/@lalanikarim/comfy-mcp-server)

> A server using FastMCP framework to generate images based on prompts via a remote Comfy server.

## Overview

This script sets up a server using the FastMCP framework to generate images based on prompts using a specified workflow. It interacts with a remote Comfy server to submit prompts and retrieve generated images.

## Prerequisites

- Python 3.x installed.
- Required packages: `mcp`, `json`, `urllib`, `time`, `os`.
- Workflow file exported from Comfy. This code uses `Flux-Dev-ComfyUI-Workflow.json` which is only used here as reference. You will need to export from your workflow and make necessary adjustments to lines [13](https://github.com/lalanikarim/comfy-mcp-server/blob/main/comfy-mcp-server.py#L13) and [24](https://github.com/lalanikarim/comfy-mcp-server/blob/main/comfy-mcp-server.py#L24).

You can install the required packages using pip:

```bash
pip install "mcp[cli]"
```

## Configuration

Set the `COMFY_URL` environment variable to point to your Comfy server URL.

Example:

```bash
export COMFY_URL=http://your-comfy-server-url:port
```

## Usage

Run the script directly:

```bash
python comfy-mcp-server.py
```

The server will start and listen for requests to generate images based on the provided prompts.

## Functionality

### `generate_image(prompt: str, ctx: Context) -> Image | str`

This function generates an image using a specified prompt. It follows these steps:

1. Checks if the `COMFY_URL` environment variable is set.
2. Loads a prompt template from a JSON file.
3. Submits the prompt to the Comfy server.
4. Polls the server for the status of the prompt processing.
5. Retrieves and returns the generated image once it's ready.

## Dependencies

- `mcp`: For setting up the FastMCP server.
- `json`: For handling JSON data.
- `urllib`: For making HTTP requests.
- `time`: For adding delays in polling.
- `os`: For accessing environment variables.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
