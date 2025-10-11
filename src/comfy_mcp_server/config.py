"""Configuration management for Comfy MCP Server."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ComfyConfig:
    """Configuration for ComfyUI MCP Server.

    Attributes:
        comfy_url: URL of the ComfyUI server
        comfy_url_external: External URL for ComfyUI (defaults to comfy_url)
        workflow_path: Path to the ComfyUI workflow JSON file
        pos_prompt_node_id: Node ID for positive prompt (auto-discovered if not set)
        neg_prompt_node_id: Node ID for negative prompt (auto-discovered if not set)
        filepath_node_id: Node ID for file path (auto-discovered if not set)
        output_node_id: Node ID for output/save image (auto-discovered if not set)
        latent_image_node_id: Node ID for latent image dimensions (auto-discovered if not set)
        output_mode: Output mode - 'file' or 'url'
        working_dir: Working directory for saving images
        comfy_output_dir: Base directory where ComfyUI saves images
        ollama_api_base: Ollama API base URL for prompt generation (optional)
        prompt_llm: Ollama model name for prompt generation (optional)
    """

    comfy_url: Optional[str]
    comfy_url_external: Optional[str]
    workflow_path: Optional[str]
    pos_prompt_node_id: Optional[str]
    neg_prompt_node_id: Optional[str]
    filepath_node_id: Optional[str]
    output_node_id: Optional[str]
    latent_image_node_id: Optional[str]
    output_mode: str
    working_dir: Optional[str]
    comfy_output_dir: str
    ollama_api_base: Optional[str]
    prompt_llm: Optional[str]

    @classmethod
    def from_environment(cls) -> "ComfyConfig":
        """Load configuration from environment variables.

        Returns:
            ComfyConfig instance populated from environment
        """
        comfy_url = os.environ.get("COMFY_URL")
        comfy_url_external = os.environ.get("COMFY_URL_EXTERNAL", comfy_url)

        # Handle backwards compatibility: PROMPT_NODE_ID takes precedence
        prompt_node_id = os.environ.get("PROMPT_NODE_ID")
        pos_prompt_node_id = (
            prompt_node_id
            if prompt_node_id
            else os.environ.get("POS_PROMPT_NODE_ID")
        )

        return cls(
            comfy_url=comfy_url,
            comfy_url_external=comfy_url_external,
            workflow_path=os.environ.get("COMFY_WORKFLOW_JSON_FILE"),
            pos_prompt_node_id=pos_prompt_node_id,
            neg_prompt_node_id=os.environ.get("NEG_PROMPT_NODE_ID"),
            filepath_node_id=os.environ.get("FILEPATH_NODE_ID"),
            output_node_id=os.environ.get("OUTPUT_NODE_ID"),
            latent_image_node_id=os.environ.get("LATENT_IMAGE_NODE_ID"),
            output_mode=os.environ.get("OUTPUT_MODE", "file"),
            working_dir=os.environ.get("COMFY_WORKING_DIR"),
            comfy_output_dir=os.environ.get(
                "COMFY_OUTPUT_DIR",
                "/Volumes/Sidecar/GenAI/ComfyUI/output"
            ),
            ollama_api_base=os.environ.get("OLLAMA_API_BASE"),
            prompt_llm=os.environ.get("PROMPT_LLM"),
        )

    def validate_required(self) -> list[str]:
        """Validate that required configuration is present.

        Returns:
            List of error messages for missing required configuration
        """
        errors = []

        if not self.comfy_url:
            errors.append("- COMFY_URL environment variable not set")

        if not self.workflow_path:
            errors.append("- COMFY_WORKFLOW_JSON_FILE environment variable not set")

        # Note: pos_prompt_node_id and output_node_id can be auto-discovered,
        # so we validate them separately after workflow loading

        return errors

    def has_ollama_config(self) -> bool:
        """Check if Ollama configuration is complete.

        Returns:
            True if both ollama_api_base and prompt_llm are set
        """
        return (
            self.ollama_api_base is not None
            and self.prompt_llm is not None
        )


# Global configuration instance
config: Optional[ComfyConfig] = None


def get_config() -> ComfyConfig:
    """Get the global configuration instance.

    Loads configuration from environment on first call.

    Returns:
        ComfyConfig instance
    """
    global config
    if config is None:
        config = ComfyConfig.from_environment()
    return config
