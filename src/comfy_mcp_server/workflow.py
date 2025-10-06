"""Workflow handling for ComfyUI."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


def workflow_to_api_format(workflow_data: dict) -> dict:
    """Convert workflow JSON to ComfyUI API prompt format.

    Converts from frontend format (with nodes array) to API format
    (dict of node_id -> node config).

    Args:
        workflow_data: Workflow data in frontend format

    Returns:
        Workflow data in API format
    """
    if "nodes" not in workflow_data:
        return workflow_data  # Already in API format

    api_format = {}
    for node in workflow_data["nodes"]:
        node_id = str(node["id"])
        inputs = {}

        # Map widget values to input names
        if "widgets_values" in node:
            # Find widget inputs
            widget_idx = 0
            for inp in node.get("inputs", []):
                if "widget" in inp:
                    # Widget input - use value from widgets_values
                    if widget_idx < len(node["widgets_values"]):
                        inputs[inp["name"]] = node["widgets_values"][widget_idx]
                        widget_idx += 1
                elif inp.get("link") is not None:
                    # Linked input - reference another node's output
                    # Find the link to get source info
                    for link in workflow_data.get("links", []):
                        if link[0] == inp["link"]:
                            source_node_id = str(link[1])
                            source_output_idx = link[2]
                            inputs[inp["name"]] = [source_node_id, source_output_idx]
                            break

        api_format[node_id] = {"class_type": node["type"], "inputs": inputs}

    return api_format


def auto_discover_node_id(
    workflow_data: dict, title_keywords: list[str], class_type: str = None
) -> Optional[str]:
    """Automatically discover a node ID by searching for keywords in title AND matching class_type.

    Args:
        workflow_data: Workflow data containing nodes
        title_keywords: List of keywords to search for in node titles
        class_type: Optional class type to match

    Returns:
        Node ID if found, None otherwise
    """
    if workflow_data is None:
        return None

    # Extract nodes array from workflow structure
    nodes = workflow_data.get("nodes", [])

    # First pass: Look for nodes with matching title keywords AND class_type
    for node in nodes:
        node_id = str(node.get("id"))
        title = node.get("title", "").lower()
        node_class = node.get("type", "")

        # If both title keyword and class_type match, this is our node
        if title and any(keyword.lower() in title for keyword in title_keywords):
            if class_type is None or node_class == class_type:
                return node_id

    # Second pass: If no title match, fall back to just class_type
    if class_type:
        for node in nodes:
            node_id = str(node.get("id"))
            node_class = node.get("type", "")
            if node_class == class_type:
                return node_id

    return None


def find_nodes_by_title(title: str, workflow_data: dict) -> list[str]:
    """Find node IDs by their title.

    Args:
        title: Title to search for
        workflow_data: Workflow data containing nodes

    Returns:
        List of matching node IDs
    """
    if "nodes" not in workflow_data:
        return []
    return [str(node["id"]) for node in workflow_data["nodes"] if node.get("title") == title]


def find_nodes_by_class(class_type: str, workflow_data: dict) -> list[str]:
    """Find node IDs by their class_type.

    Args:
        class_type: Class type to search for
        workflow_data: Workflow data containing nodes

    Returns:
        List of matching node IDs
    """
    if "nodes" not in workflow_data:
        return []
    return [
        str(node["id"]) for node in workflow_data["nodes"] if node.get("type") == class_type
    ]


def resolve_node_input(input_value, workflow_template: dict) -> str:
    """Resolve a node input that might be a reference to another node's output.

    Args:
        input_value: Either a direct value (str) or a node reference [node_id, output_idx]
        workflow_template: The API format workflow to look up node values

    Returns:
        The resolved string value
    """
    if isinstance(input_value, list) and len(input_value) == 2:
        # This is a node reference [node_id, output_idx]
        source_node_id = str(input_value[0])
        output_idx = input_value[1]

        if source_node_id in workflow_template:
            source_node = workflow_template[source_node_id]
            # For Text String nodes, get the text input that corresponds to the output index
            if source_node.get("class_type") == "Text String":
                text_inputs = ["text", "text_b", "text_c", "text_d"]
                if output_idx < len(text_inputs):
                    input_name = text_inputs[output_idx]
                    return source_node.get("inputs", {}).get(input_name, "")
        return ""
    else:
        # Direct value
        return str(input_value) if input_value is not None else ""


def evaluate_time_tokens(path_str: str) -> str:
    """Evaluate WAS time formatting tokens in a path string.

    Replaces [time(...)] tokens with actual datetime values.

    Args:
        path_str: String potentially containing [time(...)] tokens

    Returns:
        String with time tokens replaced with actual datetime values
    """
    # Find all [time(...)] patterns
    pattern = r"\[time\(([^)]+)\)\]"

    def replace_time(match):
        format_str = match.group(1)
        return datetime.now().strftime(format_str)

    return re.sub(pattern, replace_time, path_str)


def print_workflow_nodes(workflow_data: dict, workflow_path: str):
    """Print all nodes in the workflow with their IDs, titles, and class types.

    Args:
        workflow_data: Workflow data containing nodes
        workflow_path: Path to the workflow file
    """
    if workflow_data is None:
        print("Error: COMFY_WORKFLOW_JSON_FILE not set or file not found")
        return

    print("Workflow Nodes\n")
    print("=" * 80)
    print(f"Workflow: {workflow_path}\n")

    nodes = workflow_data.get("nodes", [])
    for node in nodes:
        node_id = node.get("id")
        class_type = node.get("type", "Unknown")
        title = node.get("title", "")

        title_str = f' ("{title}")' if title else ""
        print(f"  [{node_id}] {class_type}{title_str}")

    print("\n" + "-" * 80)
    print("\nCommon node types to look for:")
    print("  • Positive prompt: CLIPTextEncode with title 'Positive'")
    print("  • Negative prompt: CLIPTextEncode with title 'Negative'")
    print("  • Output: SaveImage")
    print("\n" + "=" * 80)


class WorkflowManager:
    """Manages ComfyUI workflow loading and node discovery."""

    def __init__(self, workflow_path: Optional[str]):
        """Initialize workflow manager.

        Args:
            workflow_path: Path to workflow JSON file
        """
        self.workflow_path = workflow_path
        self.workflow_data: Optional[dict] = None
        self.nodes_lookup: Optional[dict] = None
        self.api_workflow: Optional[dict] = None

        if workflow_path:
            self.load_workflow()

    def load_workflow(self):
        """Load workflow from file."""
        if not self.workflow_path:
            return

        with open(self.workflow_path, "r") as f:
            self.workflow_data = json.load(f)

        # Create lookup dict for node access
        if "nodes" in self.workflow_data:
            self.nodes_lookup = {}
            for node in self.workflow_data["nodes"]:
                node_id = str(node["id"])
                self.nodes_lookup[node_id] = node

        # Convert to API format for submission
        self.api_workflow = workflow_to_api_format(self.workflow_data)

    def discover_nodes(
        self,
        pos_prompt_override: Optional[str] = None,
        neg_prompt_override: Optional[str] = None,
        filepath_override: Optional[str] = None,
        output_override: Optional[str] = None,
    ) -> tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """Auto-discover node IDs with optional overrides.

        Args:
            pos_prompt_override: Override for positive prompt node ID
            neg_prompt_override: Override for negative prompt node ID
            filepath_override: Override for filepath node ID
            output_override: Override for output node ID

        Returns:
            Tuple of (pos_prompt_id, neg_prompt_id, filepath_id, output_id)
        """
        # Auto-discover
        pos_prompt_id = auto_discover_node_id(
            self.workflow_data, ["positive"], "CLIPTextEncode"
        )
        neg_prompt_id = auto_discover_node_id(
            self.workflow_data, ["negative"], "CLIPTextEncode"
        )
        filepath_id = auto_discover_node_id(
            self.workflow_data, ["path", "savepath"], "Text String"
        )
        output_id = auto_discover_node_id(
            self.workflow_data, ["save", "saveimage"], "Image Save"
        )

        # Apply overrides
        if pos_prompt_override:
            pos_prompt_id = pos_prompt_override
        if neg_prompt_override:
            neg_prompt_id = neg_prompt_override
        if filepath_override:
            filepath_id = filepath_override
        if output_override:
            output_id = output_override

        return pos_prompt_id, neg_prompt_id, filepath_id, output_id
