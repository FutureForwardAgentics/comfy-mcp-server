"""Tests for workflow module."""

from comfy_mcp_server.workflow import (
    auto_discover_node_id,
    evaluate_time_tokens,
    find_nodes_by_class,
    find_nodes_by_title,
    resolve_node_input,
    workflow_to_api_format,
)


class TestWorkflowConversion:
    """Test workflow conversion functions."""

    def test_workflow_to_api_format_already_api(self):
        """Test conversion when workflow is already in API format."""
        api_workflow = {
            "1": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "test"},
            }
        }

        result = workflow_to_api_format(api_workflow)
        assert result == api_workflow

    def test_workflow_to_api_format_with_nodes(self):
        """Test conversion from UI format to API format."""
        ui_workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "CLIPTextEncode",
                    "widgets_values": ["test prompt"],
                    "inputs": [{"name": "text", "widget": True}],
                }
            ],
            "links": [],
        }

        result = workflow_to_api_format(ui_workflow)

        assert "1" in result
        assert result["1"]["class_type"] == "CLIPTextEncode"
        assert result["1"]["inputs"]["text"] == "test prompt"


class TestNodeDiscovery:
    """Test node discovery functions."""

    def test_auto_discover_node_id_by_title_and_class(self):
        """Test discovering node by title and class type."""
        workflow = {
            "nodes": [
                {"id": 1, "title": "Positive Prompt", "type": "CLIPTextEncode"},
                {"id": 2, "title": "Negative Prompt", "type": "CLIPTextEncode"},
            ]
        }

        node_id = auto_discover_node_id(workflow, ["positive"], "CLIPTextEncode")
        assert node_id == "1"

    def test_auto_discover_node_id_fallback_to_class(self):
        """Test discovering node falls back to class type only."""
        workflow = {
            "nodes": [
                {"id": 1, "title": "Some Title", "type": "CLIPTextEncode"},
                {"id": 2, "title": "Another Title", "type": "SaveImage"},
            ]
        }

        node_id = auto_discover_node_id(workflow, ["positive"], "CLIPTextEncode")
        assert node_id == "1"

    def test_auto_discover_node_id_not_found(self):
        """Test discovering node returns None when not found."""
        workflow = {"nodes": [{"id": 1, "title": "Test", "type": "SomeOtherType"}]}

        node_id = auto_discover_node_id(workflow, ["positive"], "CLIPTextEncode")
        assert node_id is None

    def test_find_nodes_by_title(self):
        """Test finding nodes by exact title match."""
        workflow = {
            "nodes": [
                {"id": 1, "title": "Test Node"},
                {"id": 2, "title": "Test Node"},
                {"id": 3, "title": "Other Node"},
            ]
        }

        nodes = find_nodes_by_title("Test Node", workflow)
        assert nodes == ["1", "2"]

    def test_find_nodes_by_class(self):
        """Test finding nodes by class type."""
        workflow = {
            "nodes": [
                {"id": 1, "type": "CLIPTextEncode"},
                {"id": 2, "type": "CLIPTextEncode"},
                {"id": 3, "type": "SaveImage"},
            ]
        }

        nodes = find_nodes_by_class("CLIPTextEncode", workflow)
        assert nodes == ["1", "2"]


class TestNodeInput:
    """Test node input resolution."""

    def test_resolve_node_input_direct_value(self):
        """Test resolving a direct input value."""
        value = resolve_node_input("direct_value", {})
        assert value == "direct_value"

    def test_resolve_node_input_node_reference(self):
        """Test resolving a node reference input."""
        workflow = {
            "1": {
                "class_type": "Text String",
                "inputs": {"text": "referenced_value"},
            }
        }

        value = resolve_node_input(["1", 0], workflow)
        assert value == "referenced_value"

    def test_resolve_node_input_none(self):
        """Test resolving None input."""
        value = resolve_node_input(None, {})
        assert value == ""


class TestTimeTokens:
    """Test time token evaluation."""

    def test_evaluate_time_tokens(self):
        """Test evaluating time tokens in path."""
        import re
        from datetime import datetime

        path = "/output/[time(%Y-%m-%d)]/images"
        result = evaluate_time_tokens(path)

        # Should have replaced the time token
        assert "[time" not in result
        # Should contain today's date
        today = datetime.now().strftime("%Y-%m-%d")
        assert today in result

    def test_evaluate_time_tokens_no_tokens(self):
        """Test path without time tokens remains unchanged."""
        path = "/output/images"
        result = evaluate_time_tokens(path)
        assert result == path
