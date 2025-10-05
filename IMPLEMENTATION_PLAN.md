# Comfy MCP Server Refactoring Plan

## Stage 1: Remove Third-Party References & Clean Repository
**Goal**: Remove all smithery.ai references and clean up repository
**Success Criteria**: No smithery references, clean git status
**Tests**: Manual verification of removed files and updated documentation
**Status**: Not Started

### Tasks:
- [ ] Remove `smithery.yaml` file
- [ ] Remove smithery badge from README.md
- [ ] Update Dockerfile (remove smithery comments, modernize)
- [ ] Add `.DS_Store` to .gitignore
- [ ] Remove tracked `.DS_Store` files from git

## Stage 2: Extract Configuration Module
**Goal**: Centralize all configuration and environment variable handling
**Success Criteria**: All config in dedicated module, no env vars in main code
**Tests**: Server starts correctly with existing env vars
**Status**: Not Started

### Tasks:
- [ ] Create `src/comfy_mcp_server/config.py`
- [ ] Move all environment variable loading to config module
- [ ] Create Config dataclass with validation
- [ ] Add configuration error messages
- [ ] Update main module to use config

## Stage 3: Extract Workflow Module
**Goal**: Separate workflow handling logic from main module
**Success Criteria**: Workflow operations isolated, main module cleaner
**Tests**: Workflow loading and node discovery work correctly
**Status**: Not Started

### Tasks:
- [ ] Create `src/comfy_mcp_server/workflow.py`
- [ ] Move workflow conversion functions
- [ ] Move node discovery functions
- [ ] Move workflow inspection utilities
- [ ] Update main module to use workflow module

## Stage 4: Extract Image Operations Module
**Goal**: Isolate ComfyUI API and image handling
**Success Criteria**: Clean separation of concerns, no hardcoded paths
**Tests**: Image generation works end-to-end
**Status**: Not Started

### Tasks:
- [ ] Create `src/comfy_mcp_server/comfy_client.py`
- [ ] Move submit_workflow, poll_for_completion functions
- [ ] Move image download/save functions
- [ ] Replace hardcoded `/Volumes/Sidecar/GenAI/ComfyUI/output` with config
- [ ] Add proper error handling
- [ ] Remove debug print statements

## Stage 5: Refactor Main Module & Add Type Safety
**Goal**: Clean up main module, add type hints, improve code quality
**Success Criteria**: Type hints complete, functions < 30 lines, follows PEP 8
**Tests**: All functionality preserved, type checking passes
**Status**: Not Started

### Tasks:
- [ ] Refactor generate_image function (break into smaller functions)
- [ ] Add comprehensive type hints to all modules
- [ ] Add/improve docstrings
- [ ] Extract constants and magic values
- [ ] Update README with new structure
- [ ] Add example configuration file

## Stage 6: Add Professional Structure
**Goal**: Add tests, improve documentation, finalize professional structure
**Success Criteria**: Test coverage, clear documentation, example configs
**Tests**: pytest suite passes
**Status**: Not Started

### Tasks:
- [ ] Create basic test structure
- [ ] Add unit tests for config module
- [ ] Add unit tests for workflow module
- [ ] Create `.env.example` file
- [ ] Update README with architecture overview
- [ ] Add CONTRIBUTING.md
