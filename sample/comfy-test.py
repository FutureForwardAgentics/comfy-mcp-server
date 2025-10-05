import os
import sys

sys.path.insert(0, "/Volumes/Sidecar/FFAI/The Lands Between Time/comfy-mcp-server/src")
os.environ["COMFY_URL"] = "http://127.0.0.1:8642"
os.environ["COMFY_WORKFLOW_JSON_FILE"] = (
    "/Volumes/Sidecar/GenAI/ComfyUI/user/default/workflows/image_chroma1_radiance_text_to_image_api.json"
)
os.environ["OUTPUT_MODE"] = "file"

from comfy_mcp_server import generate_image

result = generate_image(
    positive_prompt="Premium sci-fi game card template, three distinct sections, top banner panel for title, large middle portrait frame with minimal geometric border, bottom text panel, deep purple to indigo gradient background, subtle gold geometric line accents, clean professional layout, Foundation universe aesthetic, sleek interface design, high quality digital art, sharp details, 4k",
    negative_prompt="fantasy, medieval, ornate decorations, card back, symmetrical center, filled portrait, faces, text, characters, cluttered patterns, no divisions, merged sections, dragons, magic circles, busy design, blurry, low quality",
    save_path="/Volumes/Sidecar/FFAI/The Lands Between Time/the-mules-court/img",
    ctx=None,
)

print(result)
