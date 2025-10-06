"""ComfyUI API client for image generation."""

import json
import os
import time
import urllib.request
from datetime import datetime
from typing import Optional, Tuple

from mcp.server.fastmcp import Context

from .workflow import resolve_node_input, evaluate_time_tokens


class ComfyClient:
    """Client for interacting with ComfyUI API."""

    def __init__(
        self,
        comfy_url: str,
        comfy_url_external: Optional[str] = None,
        comfy_output_dir: str = None,
    ):
        """Initialize ComfyUI client.

        Args:
            comfy_url: URL of the ComfyUI server
            comfy_url_external: External URL for file access (defaults to comfy_url)
            comfy_output_dir: Base directory where ComfyUI saves images
        """
        self.comfy_url = comfy_url
        self.comfy_url_external = comfy_url_external or comfy_url
        self.comfy_output_dir = comfy_output_dir

    def submit_workflow(self, workflow: dict, ctx: Optional[Context] = None) -> Optional[str]:
        """Submit workflow to ComfyUI and return prompt_id.

        Args:
            workflow: Workflow configuration in API format
            ctx: Optional MCP context for logging

        Returns:
            Prompt ID if successful, None otherwise
        """
        payload = {"prompt": workflow}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(f"{self.comfy_url}/prompt", data)
        resp = urllib.request.urlopen(req)

        if resp.status != 200:
            return None

        if ctx:
            ctx.info("Submitted prompt")
        resp_data = json.loads(resp.read())
        return resp_data.get("prompt_id")

    def poll_for_completion(
        self, prompt_id: str, ctx: Optional[Context] = None, max_attempts: int = 60
    ) -> Optional[dict]:
        """Poll ComfyUI history API until workflow completes or times out.

        Args:
            prompt_id: ID of the prompt to check
            ctx: Optional MCP context for logging
            max_attempts: Maximum number of polling attempts (default 60)

        Returns:
            History data if completed, None if timed out
        """
        for _ in range(max_attempts):
            history_req = urllib.request.Request(f"{self.comfy_url}/history/{prompt_id}")
            history_resp = urllib.request.urlopen(history_req)

            if history_resp.status == 200:
                if ctx:
                    ctx.info("Checking status...")
                history_data = json.loads(history_resp.read())

                if prompt_id in history_data:
                    if history_data[prompt_id]["status"]["completed"]:
                        return history_data[prompt_id]

            time.sleep(5)

        return None

    def find_latest_image_in_output(
        self, output_node_config: dict, workflow_template: dict
    ) -> str:
        """Find the latest image file from ComfyUI output directory.

        Args:
            output_node_config: The SaveImage or Image Save node configuration
            workflow_template: The API format workflow for resolving node references

        Returns:
            Full path to the most recently created image file

        Raises:
            ValueError: If output directory not found or no images found
        """
        if not self.comfy_output_dir:
            raise ValueError("COMFY_OUTPUT_DIR not configured")

        base_output_dir = self.comfy_output_dir
        node_class = output_node_config.get("class_type", "")

        # Handle WAS "Image Save" node
        if node_class == "Image Save":
            # Get output_path (may be a node reference or direct value)
            output_path_input = output_node_config.get("inputs", {}).get("output_path", "")
            output_path = resolve_node_input(output_path_input, workflow_template)

            # Evaluate time tokens in the output path
            output_path = evaluate_time_tokens(output_path)

            # Build the search directory
            if output_path:
                search_dir = os.path.join(base_output_dir, output_path)
            else:
                search_dir = base_output_dir

        # Handle standard ComfyUI "SaveImage" node
        else:
            # Extract filename_prefix from SaveImage node to determine subdirectory
            filename_prefix = output_node_config.get("inputs", {}).get(
                "filename_prefix", ""
            )

            # Parse the filename_prefix to extract directory path
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
        self,
        output_node_config: dict,
        workflow_template: dict,
        save_path: str,
        ctx: Optional[Context] = None,
    ) -> Tuple[bytes, str]:
        """Download generated image from ComfyUI and save to local disk.

        Args:
            output_node_config: Output node configuration
            workflow_template: The API format workflow
            save_path: Absolute path to directory where image should be saved locally
            ctx: Optional MCP context for logging

        Returns:
            Tuple of (image_bytes, full_path) where full_path is the local saved file path

        Raises:
            ValueError: If output node not found or image cannot be located
        """
        # Find the most recently created image file based on SaveImage config
        source_path = self.find_latest_image_in_output(output_node_config, workflow_template)
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
