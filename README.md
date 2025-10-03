# Comfy MCP Server

[![smithery badge](https://smithery.ai/badge/@lalanikarim/comfy-mcp-server)](https://smithery.ai/server/@lalanikarim/comfy-mcp-server)

> A server using FastMCP framework to generate images based on prompts via a remote Comfy server.

## Overview

This MCP server uses the FastMCP framework to generate images based on prompts using a specified workflow. It interacts with a remote ComfyUI server to submit prompts, retrieve generated images, and save them to disk.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) package and project manager for Python.
- Workflow file exported from Comfy UI. This code includes a sample `Flux-Dev-ComfyUI-Workflow.json` which is only used here as reference. You will need to export from your workflow and set the environment variables accordingly.

You can install the required packages for local development:

```bash
uvx mcp[cli]
```

## Configuration

Set the following environment variables:

- `COMFY_URL` to point to your Comfy server URL.
- `COMFY_WORKFLOW_JSON_FILE` to point to the absolute path of the API export json file for the comfyui workflow.
- `POS_PROMPT_NODE_ID` to the id of the positive text prompt node (or use legacy `PROMPT_NODE_ID`).
- `NEG_PROMPT_NODE_ID` to the id of the negative text prompt node (optional).
- `OUTPUT_NODE_ID` to the id of the output node with the final image.
- `OUTPUT_MODE` to either `url` or `file` to select desired output.
- `COMFY_WORKING_DIR` to set the default directory for saving images (optional, defaults to current working directory).

**Note on backwards compatibility:** `PROMPT_NODE_ID` is still supported and takes precedence over `POS_PROMPT_NODE_ID`. If only `PROMPT_NODE_ID` is set, it will be used as the `POS_PROMPT_NODE_ID` variable.

Optionally, if you have an [Ollama](https://ollama.com) server running, you can connect to it for prompt generation.

- `OLLAMA_API_BASE` to the url where ollama is running.
- `PROMPT_LLM` to the name of the model hosted on ollama for prompt generation.

Example:

```bash
export COMFY_URL=http://your-comfy-server-url:port
export COMFY_WORKFLOW_JSON_FILE=/path/to/the/comfyui_workflow_export.json
export POS_PROMPT_NODE_ID=6 # positive prompt node id
export NEG_PROMPT_NODE_ID=7 # negative prompt node id (optional)
export OUTPUT_NODE_ID=9 # use the correct node id here
export OUTPUT_MODE=file
export COMFY_WORKING_DIR=/path/to/your/working/directory # optional, defaults to current directory
```

## Usage

Comfy MCP Server can be launched by the following command:

```bash
uvx comfy-mcp-server
```

### Example Claude Desktop Config

For published package from PyPI:

```json
{
  "mcpServers": {
    "Comfy MCP Server": {
      "command": "/path/to/uvx",
      "args": ["comfy-mcp-server"],
      "env": {
        "COMFY_URL": "http://your-comfy-server-url:port",
        "COMFY_WORKFLOW_JSON_FILE": "/path/to/the/comfyui_workflow_export.json",
        "POS_PROMPT_NODE_ID": "6",
        "NEG_PROMPT_NODE_ID": "7",
        "OUTPUT_NODE_ID": "9",
        "OUTPUT_MODE": "file",
        "COMFY_WORKING_DIR": "/path/to/your/working/directory"
      }
    }
  }
}
```

For local development version:

```json
{
  "mcpServers": {
    "Comfy MCP Server": {
      "command": "/path/to/uvx",
      "args": ["--from", "/path/to/comfy-mcp-server", "comfy-mcp-server"],
      "env": {
        "COMFY_URL": "http://your-comfy-server-url:port",
        "COMFY_WORKFLOW_JSON_FILE": "/path/to/the/comfyui_workflow_export.json",
        "POS_PROMPT_NODE_ID": "6",
        "NEG_PROMPT_NODE_ID": "7",
        "OUTPUT_NODE_ID": "9",
        "OUTPUT_MODE": "file",
        "COMFY_WORKING_DIR": "/path/to/your/working/directory"
      }
    }
  }
}
```

## Functionality

### `generate_image(positive_prompt: str, negative_prompt: str = "", save_path: str = None, ctx: Context = None) -> Image | str`

This function generates an image using specified prompts. It follows these steps:

1. Checks if all the environment variables are set.
2. Loads a prompt template from a JSON file.
3. Sets the positive prompt (and optionally the negative prompt) in the workflow.
4. Submits the prompt to the Comfy server.
5. Polls the server for the status of the prompt processing.
6. Retrieves the generated image once it's ready.
7. Saves the image to disk at the specified location.
8. Returns the generated image.

**Parameters:**

- `positive_prompt`: The positive prompt describing what to generate
- `negative_prompt`: The negative prompt describing what to avoid (optional, default: "")
- `save_path`: Directory to save generated images (optional, default: `{COMFY_WORKING_DIR}/img/` or `./img/`)
- `ctx`: MCP context for logging

### `generate_prompt(topic: str, ctx: Context) -> str`

This function generates a comprehensive image generation prompt from specified topic.

## Dependencies

- `mcp`: For setting up the FastMCP server.
- `json`: For handling JSON data.
- `urllib`: For making HTTP requests.
- `time`: For adding delays in polling.
- `os`: For accessing environment variables.
- `langchain`: For creating simple LLM Prompt chain to generate image generation prompt from topic.
- `langchain-ollama`: For ollama specific modules for LangChain.

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/lalanikarim/comfy-mcp-server/blob/main/LICENSE) file for details.
