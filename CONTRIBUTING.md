# Contributing to Comfy MCP Server

Thank you for your interest in contributing to Comfy MCP Server!

## Development Setup

### Prerequisites

- Python 3.13 or later
- [uv](https://docs.astral.sh/uv/) for package management
- A running ComfyUI instance for testing

### Installation

1. Clone the repository:
```bash
git clone https://github.com/lalanikarim/comfy-mcp-server.git
cd comfy-mcp-server
```

2. Install dependencies:
```bash
uv sync
```

3. Copy the example environment file and configure:
```bash
cp .env.example .env
# Edit .env with your settings
```

## Project Structure

```
comfy-mcp-server/
├── src/
│   └── comfy_mcp_server/
│       ├── __init__.py        # Main MCP server and tools
│       ├── config.py          # Configuration management
│       ├── workflow.py        # Workflow handling and node discovery
│       └── comfy_client.py    # ComfyUI API client
├── tests/                     # Test suite
├── sample/                    # Example workflows
└── pyproject.toml            # Project metadata and dependencies
```

## Code Style

This project follows:
- [PEP 8](https://pep8.org/) for Python style
- Type hints for all functions
- Docstrings for all public functions and classes

### Type Hints

All functions should include type hints:

```python
def example_function(param: str, optional: Optional[int] = None) -> bool:
    """Brief description of function.

    Args:
        param: Description of parameter
        optional: Description of optional parameter

    Returns:
        Description of return value
    """
    return True
```

## Testing

Run tests with pytest:

```bash
uv run pytest
```

Run tests with coverage:

```bash
uv run pytest --cov=comfy_mcp_server --cov-report=html
```

### Writing Tests

- Place tests in the `tests/` directory
- Name test files with `test_` prefix
- Use descriptive test names that explain what is being tested
- Follow the Arrange-Act-Assert pattern

Example:

```python
def test_config_validates_required_fields():
    """Test that config validation catches missing required fields."""
    # Arrange
    config = ComfyConfig(comfy_url=None, ...)

    # Act
    errors = config.validate_required()

    # Assert
    assert len(errors) > 0
    assert "COMFY_URL" in " ".join(errors)
```

## Architecture

### Configuration (`config.py`)

- `ComfyConfig`: Dataclass holding all configuration
- `get_config()`: Returns global configuration instance
- Configuration is loaded from environment variables

### Workflow Management (`workflow.py`)

- `WorkflowManager`: Handles workflow loading and node discovery
- `workflow_to_api_format()`: Converts UI format to API format
- `auto_discover_node_id()`: Finds nodes by title/class
- Node discovery tries title+class first, then falls back to class only

### ComfyUI Client (`comfy_client.py`)

- `ComfyClient`: Handles all ComfyUI API communication
- `submit_workflow()`: Submits workflow to ComfyUI
- `poll_for_completion()`: Polls for workflow completion
- `download_and_save_image()`: Downloads and saves generated images

### Main Module (`__init__.py`)

- Registers MCP tools
- `generate_image()`: Main tool for image generation
- `generate_prompt()`: Optional tool for prompt generation (requires Ollama)

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes following the code style guidelines
4. Add tests for any new functionality
5. Ensure all tests pass: `uv run pytest`
6. Update documentation if needed
7. Commit your changes with clear, descriptive messages
8. Push to your fork and submit a pull request

## Commit Messages

Follow conventional commits format:

- `feat: Add new feature`
- `fix: Fix bug`
- `docs: Update documentation`
- `test: Add or update tests`
- `refactor: Code refactoring`
- `chore: Maintenance tasks`

## Questions or Issues?

- Open an issue on GitHub
- Provide clear reproduction steps for bugs
- Include relevant logs and configuration (redact sensitive info)

Thank you for contributing!
