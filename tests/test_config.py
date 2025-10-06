"""Tests for configuration module."""

import os
from unittest import mock

import pytest

from comfy_mcp_server.config import ComfyConfig


class TestComfyConfig:
    """Test ComfyConfig class."""

    def test_from_environment_with_all_vars(self):
        """Test loading configuration from environment variables."""
        env_vars = {
            "COMFY_URL": "http://localhost:8188",
            "COMFY_WORKFLOW_JSON_FILE": "/path/to/workflow.json",
            "POS_PROMPT_NODE_ID": "1",
            "NEG_PROMPT_NODE_ID": "2",
            "OUTPUT_NODE_ID": "3",
            "OUTPUT_MODE": "file",
            "COMFY_WORKING_DIR": "/tmp/comfy",
            "COMFY_OUTPUT_DIR": "/tmp/output",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = ComfyConfig.from_environment()

        assert config.comfy_url == "http://localhost:8188"
        assert config.workflow_path == "/path/to/workflow.json"
        assert config.pos_prompt_node_id == "1"
        assert config.neg_prompt_node_id == "2"
        assert config.output_node_id == "3"
        assert config.output_mode == "file"
        assert config.working_dir == "/tmp/comfy"
        assert config.comfy_output_dir == "/tmp/output"

    def test_from_environment_with_defaults(self):
        """Test configuration defaults."""
        env_vars = {
            "COMFY_URL": "http://localhost:8188",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = ComfyConfig.from_environment()

        assert config.output_mode == "file"  # default
        assert config.comfy_output_dir == "/Volumes/Sidecar/GenAI/ComfyUI/output"  # default

    def test_validate_required_missing_url(self):
        """Test validation fails when COMFY_URL is missing."""
        config = ComfyConfig(
            comfy_url=None,
            comfy_url_external=None,
            workflow_path="/path/to/workflow.json",
            pos_prompt_node_id=None,
            neg_prompt_node_id=None,
            filepath_node_id=None,
            output_node_id=None,
            output_mode="file",
            working_dir=None,
            comfy_output_dir="/tmp",
            ollama_api_base=None,
            prompt_llm=None,
        )

        errors = config.validate_required()
        assert "COMFY_URL" in " ".join(errors)

    def test_validate_required_missing_workflow(self):
        """Test validation fails when workflow path is missing."""
        config = ComfyConfig(
            comfy_url="http://localhost:8188",
            comfy_url_external="http://localhost:8188",
            workflow_path=None,
            pos_prompt_node_id=None,
            neg_prompt_node_id=None,
            filepath_node_id=None,
            output_node_id=None,
            output_mode="file",
            working_dir=None,
            comfy_output_dir="/tmp",
            ollama_api_base=None,
            prompt_llm=None,
        )

        errors = config.validate_required()
        assert "COMFY_WORKFLOW_JSON_FILE" in " ".join(errors)

    def test_has_ollama_config_true(self):
        """Test Ollama configuration detection when both values present."""
        config = ComfyConfig(
            comfy_url="http://localhost:8188",
            comfy_url_external="http://localhost:8188",
            workflow_path="/path/to/workflow.json",
            pos_prompt_node_id=None,
            neg_prompt_node_id=None,
            filepath_node_id=None,
            output_node_id=None,
            output_mode="file",
            working_dir=None,
            comfy_output_dir="/tmp",
            ollama_api_base="http://localhost:11434",
            prompt_llm="llama2",
        )

        assert config.has_ollama_config() is True

    def test_has_ollama_config_false(self):
        """Test Ollama configuration detection when values missing."""
        config = ComfyConfig(
            comfy_url="http://localhost:8188",
            comfy_url_external="http://localhost:8188",
            workflow_path="/path/to/workflow.json",
            pos_prompt_node_id=None,
            neg_prompt_node_id=None,
            filepath_node_id=None,
            output_node_id=None,
            output_mode="file",
            working_dir=None,
            comfy_output_dir="/tmp",
            ollama_api_base=None,
            prompt_llm=None,
        )

        assert config.has_ollama_config() is False

    def test_backwards_compatibility_prompt_node_id(self):
        """Test backwards compatibility with PROMPT_NODE_ID."""
        env_vars = {
            "COMFY_URL": "http://localhost:8188",
            "PROMPT_NODE_ID": "old_id",
        }

        with mock.patch.dict(os.environ, env_vars, clear=True):
            config = ComfyConfig.from_environment()

        assert config.pos_prompt_node_id == "old_id"
