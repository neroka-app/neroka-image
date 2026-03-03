#!/usr/bin/env python3
"""
neroka-gemini/generate.py — PREFERRED IMAGE GENERATION SKILL
Uses google/gemini-3.1-flash-image-preview via OpenRouter.

This is the preferred way to generate images. Better at following instructions,
less restrictive than nano-banana-2, supports img2img natively via multimodal input.
Image data returned in message.images (OpenRouter-specific field).

Usage:
    python3 generate.py "prompt here"
    python3 generate.py "prompt here" --input path/to/image.png
    python3 generate.py "prompt here" --input img.png --output-dir /custom/dir
    python3 generate.py "prompt here" --no-ref  # skip default face ref
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-3.1-flash-image-preview"

DEFAULT_REF = Path(__file__).parent.parent.parent / "neroka_face_ref.png"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent.parent / "neroka_generated"

REFERENCE_PREFIX = (
    "The provided reference image shows a character from multiple angles. "
    "Use this reference to accurately reproduce the character's appearance — "
    "crimson-red wavy hair, fair porcelain skin, East Asian features, reddish eyes. "
    "Generate a new image of this character: "
)


def get_api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        env_file = Path.home() / ".openclaw" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        print("Error: OPENROUTER_API_KEY not found", file=sys.stderr)
        sys.exit(1)
    return key


def compress_image(path: Path, max_size_mb=3.5, max_px=2048) -> tuple[str, str]:
    """Compress image if needed. Returns (base64_data, mime_type)."""
    size_mb = path.stat().st_size / (1024 * 1024)
    ext = path.suffix.lower().lstrip(".")

    if size_mb > max_size_mb:
        tmp = Path("/tmp") / f"neroka_gemini_input_{path.stem}.jpg"
        subprocess.run(
            ["convert", str(path), "-resize", f"{max_px}x{max_px}>", "-quality", "85", str(tmp)],
            check=True, capture_output=True
        )
        path = tmp
        ext = "jpg"
        print(f"(compressed to {path.stat().st_size // 1024}KB)", file=sys.stderr)

    mime_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}
    mime = f"image/{mime_map.get(ext, 'jpeg')}"
    data = base64.b64encode(path.read_bytes()).decode()
    return data, mime


def generate(prompt: str, input_image: Path = None, use_ref: bool = True,
             output_dir: Path = DEFAULT_OUTPUT_DIR, api_key: str = None) -> Path:
    if not api_key:
        api_key = get_api_key()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    content = []

    # Build prompt text
    final_prompt = prompt
    if use_ref and input_image is None:
        # Ref-only generation
        final_prompt = REFERENCE_PREFIX + prompt

    content.append({"type": "text", "text": final_prompt})

    # Add reference image if no input scene
    if use_ref and input_image is None and DEFAULT_REF.exists():
        ref_data, ref_mime = compress_image(DEFAULT_REF)
        content.append({"type": "image_url", "image_url": {"url": f"data:{ref_mime};base64,{ref_data}"}})

    # Add input scene image
    if input_image and input_image.exists():
        img_data, img_mime = compress_image(input_image)
        content.append({"type": "image_url", "image_url": {"url": f"data:{img_mime};base64,{img_data}"}})

    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": content}]
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-Title": "Neroka"
        }
    )

    print(f"Generating with {MODEL}...", file=sys.stderr)

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP Error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)

    msg = result["choices"][0]["message"]
    images = msg.get("images", [])
    usage = result.get("usage", {})
    cost = usage.get("cost", 0)

    if not images:
        # Check content too
        content_out = msg.get("content")
        if isinstance(content_out, list):
            for item in content_out:
                if item.get("type") == "image_url":
                    images = [item]
                    break
        if not images:
            print(f"No image in response. Content: {str(content_out)[:200]}", file=sys.stderr)
            sys.exit(1)

    # Save image
    img_url = images[0]["image_url"]["url"]
    if img_url.startswith("data:"):
        img_bytes = base64.b64decode(img_url.split(",")[1])
    else:
        with urllib.request.urlopen(img_url) as r:
            img_bytes = r.read()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    out_path = output_dir / f"neroka-{ts}.png"
    out_path.write_bytes(img_bytes)

    # Upscale to 2k by default
    upscaled = output_dir / f"neroka-{ts}-2k.png"
    subprocess.run(
        ["convert", str(out_path), "-resize", "2048x2048", "-filter", "Lanczos", str(upscaled)],
        check=True, capture_output=True
    )
    out_path.unlink()  # remove 1k original
    upscaled.rename(out_path)

    print(f"Cost: ${cost:.4f} | Saved to: {out_path}")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="Neroka Gemini Image Generator (PREFERRED)")
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument("--input", type=Path, help="Input image for img2img / style reference")
    parser.add_argument("--no-ref", action="store_true", help="Skip default face reference")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    out = generate(
        prompt=args.prompt,
        input_image=args.input,
        use_ref=not args.no_ref,
        output_dir=args.output_dir
    )

    print(f"Done: {out}")


if __name__ == "__main__":
    main()
