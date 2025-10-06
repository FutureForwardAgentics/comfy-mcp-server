FROM python:3.13-slim-bookworm

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/ ./src/

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

ENV COMFY_URL="" \
    COMFY_WORKFLOW_JSON_FILE="" \
    POS_PROMPT_NODE_ID="" \
    NEG_PROMPT_NODE_ID="" \
    OUTPUT_NODE_ID="" \
    OUTPUT_MODE="file" \
    COMFY_WORKING_DIR="/app/output"

ENTRYPOINT ["comfy-mcp-server"]
