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
    positive_prompt="Playing card front template, mystical deep purple background with gradient, ornate Art Nouveau style golden borders and decorative frames, multiple empty framed sections for card information, sci-fi Foundation universe aesthetic, elegant geometric patterns, intricate filigree details, beige and cream colored frames with gold accents, symmetrical layout, professional game card design, clean empty spaces for text and artwork, luxurious royal appearance, psychohistory and galactic empire theme, high quality vector-style illustration",
    negative_prompt="photorealistic, modern minimalist, cluttered, text, characters, people, low quality, blurry, pixelated, messy, asymmetric, crowded, busy background, watermark, signature, rough edges, amateur, simple borders, plain design, dull colors",
    save_path="/Volumes/Sidecar/FFAI/The Lands Between Time/the-mules-court/img/",
)

if hasattr(result, '__class__') and result.__class__.__name__ == 'Image':
    print("✓ Image generated successfully")
    print(f"  Format: {result.format if hasattr(result, 'format') else 'unknown'}")
    print(f"  Size: {len(result.data) if hasattr(result, 'data') else 'unknown'} bytes")
else:
    print(f"Result: {result}")
