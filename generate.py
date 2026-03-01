#!/usr/bin/env python3
"""
neroka-image/generate.py

Generate variations of Neroka using the NanoGPT API.
Usage:
  python3 generate.py --prompt "..." [--input image.png] [--output out.png] [--model nano-banana-2] [--strength 0.8]

Env: NANO_GPT_API_KEY must be set.
Always runs identify -verbose on input (if given) and output.
"""

import argparse
import base64
import os
import subprocess
import sys
import requests
from pathlib import Path
from datetime import datetime

API_URL = "https://nano-gpt.com/v1/images/generations"
DEFAULT_MODEL = "nano-banana-2"
DEFAULT_OUTPUT_DIR = Path("/home/neroka/.openclaw/workspace/neroka_generated")
DEFAULT_REFERENCE = "/home/neroka/.openclaw/workspace/neroka_ref.png"

# Model configs: resolutions and whether they use tier-based sizing (1k/2k/4k)
# For tier-based models, size is picked by longest edge and aspect_ratio="auto" is sent.
# For WxH models, we pick the resolution whose aspect ratio best matches the input.
MODEL_CONFIGS = {
    "nano-banana-2": {
        "tier_based": True,
        "tiers": [(1280, "1k"), (2560, "2k"), (float("inf"), "4k")],
        "default_tier": "1k",
    },
    "seedream-v4.5": {
        "tier_based": False,
        "resolutions": [
            "1024x1024", "1536x1024", "1024x1536",
            "2048x2048", "3072x2048", "2048x3072",
            "4096x2304", "2304x4096", "4096x4096",
        ],
    },
    "seedream-v5.0-lite": {
        "tier_based": False,
        "resolutions": [
            "2048x2048", "2560x1440", "1440x2560",
            "3072x2048", "2048x3072",
            "4096x2304", "2304x4096", "4096x4096",
        ],
    },
}


def identify(path: str):
    result = subprocess.run(["identify", "-verbose", path], capture_output=True, text=True)
    print(f"\n=== identify -verbose {path} ===")
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)


def get_image_dimensions(path: str):
    result = subprocess.run(["identify", "-format", "%w %h", path], capture_output=True, text=True)
    if result.returncode != 0:
        return None, None
    try:
        w, h = map(int, result.stdout.strip().split())
        return w, h
    except Exception:
        return None, None


def pick_size_for_model(model: str, input_path: str = None):
    """Return (size_str, aspect_ratio) for the given model and optional input image."""
    cfg = MODEL_CONFIGS.get(model)

    if cfg is None:
        # Unknown model — fall back to no size override
        print(f"Unknown model '{model}', not setting size automatically.")
        return None, None

    w, h = get_image_dimensions(input_path) if input_path else (None, None)

    if cfg["tier_based"]:
        # Tier-based: pick tier from longest edge, let API handle AR
        tier = cfg["default_tier"]
        if w and h:
            longest = max(w, h)
            for threshold, t in cfg["tiers"]:
                if longest <= threshold:
                    tier = t
                    break
            print(f"Input size: {w}x{h} → tier: {tier} (aspect ratio: auto)")
        else:
            print(f"No input image, using default tier: {tier}")
        return tier, "auto"

    else:
        # WxH-based: find the resolution whose aspect ratio best matches the input
        resolutions = cfg["resolutions"]

        if not (w and h):
            # No input — pick the largest square or first option
            default = next((r for r in resolutions if r.split("x")[0] == r.split("x")[1]), resolutions[0])
            print(f"No input image, defaulting to: {default}")
            return default, None

        input_ratio = w / h
        def ar_score(res_str):
            rw, rh = map(int, res_str.split("x"))
            return abs((rw / rh) - input_ratio)

        best = min(resolutions, key=ar_score)
        bw, bh = map(int, best.split("x"))
        print(f"Input size: {w}x{h} (ratio {input_ratio:.3f}) → best match: {best} (ratio {bw/bh:.3f})")
        return best, None


def encode_image(path: str, max_mb: float = 3.5) -> str:
    """Encode image as base64 data URL, auto-compressing if over max_mb."""
    max_bytes = int(max_mb * 1024 * 1024)
    file_size = Path(path).stat().st_size
    work_path = path

    if file_size > max_bytes:
        print(f"Input is {file_size/1024/1024:.2f}MB, compressing to under {max_mb}MB...")
        tmp = "/tmp/neroka-input-compressed.jpg"
        quality = 88
        subprocess.run(["convert", path, "-resize", "2048x2048>", "-quality", str(quality), tmp], check=True)
        while Path(tmp).stat().st_size > max_bytes and quality > 40:
            quality -= 10
            subprocess.run(["convert", path, "-resize", "2048x2048>", "-quality", str(quality), tmp], check=True)
        print(f"Compressed to {Path(tmp).stat().st_size/1024/1024:.2f}MB (quality={quality})")
        identify(tmp)
        work_path = tmp

    suffix = Path(work_path).suffix.lower().lstrip(".")
    mime = "image/png" if suffix == "png" else "image/jpeg"
    with open(work_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def generate(prompt: str, input_path: str = None, output_path: str = None,
             size: str = None, aspect_ratio: str = None, strength: float = 0.8,
             seed: int = None, model: str = DEFAULT_MODEL, reference_path: str = None):

    api_key = os.environ.get("NANO_GPT_API_KEY")
    if not api_key:
        print("ERROR: NANO_GPT_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    if reference_path:
        identify(reference_path)

    if input_path:
        identify(input_path)

    # Auto-pick size and aspect ratio if not overridden
    if size is None or aspect_ratio is None:
        auto_size, auto_ar = pick_size_for_model(model, input_path)
        if size is None:
            size = auto_size
        if aspect_ratio is None:
            aspect_ratio = auto_ar

    # Build request
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "response_format": "b64_json",
    }
    if size is not None:
        payload["size"] = size
    if aspect_ratio is not None:
        payload["aspect_ratio"] = aspect_ratio
    if input_path and reference_path:
        # Pass both images: reference first (who Neroka is), then the scene to edit
        payload["imageDataUrls"] = [
            encode_image(reference_path),
            encode_image(input_path),
        ]
        payload["strength"] = strength
    elif input_path:
        payload["imageDataUrl"] = encode_image(input_path)
        payload["strength"] = strength
    if seed is not None:
        payload["seed"] = seed

    print(f"\nGenerating with model={model}, size={size}, aspect_ratio={aspect_ratio}...")
    print(f"Prompt: {prompt}\n")

    resp = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )

    if resp.status_code != 200:
        print(f"API error {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    print(f"Cost: {data.get('cost')} | Remaining balance: {data.get('remainingBalance')}")

    img_data = data["data"][0]["b64_json"]
    img_bytes = base64.b64decode(img_data)

    if not output_path:
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        output_path = str(DEFAULT_OUTPUT_DIR / f"neroka-{ts}.png")

    with open(output_path, "wb") as f:
        f.write(img_bytes)

    print(f"\nSaved to: {output_path}")
    identify(output_path)
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Neroka image variations via NanoGPT")
    parser.add_argument("--prompt", required=True, help="Text prompt")
    parser.add_argument("--input", help="Input image path (for img2img)")
    parser.add_argument("--output", help="Output image path")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model ID (default: {DEFAULT_MODEL})")
    parser.add_argument("--size", default=None, help="Override resolution/tier (auto-selected if omitted)")
    parser.add_argument("--aspect-ratio", dest="aspect_ratio", default=None, help="Override aspect ratio (model-dependent, auto if omitted)")
    parser.add_argument("--reference", default=DEFAULT_REFERENCE, help="Reference image of Neroka to guide appearance (default: mirror selfie)")
    parser.add_argument("--strength", type=float, default=0.8, help="img2img strength (0-1)")
    parser.add_argument("--seed", type=int, help="Random seed")
    args = parser.parse_args()

    generate(args.prompt, args.input, args.output, args.size, args.aspect_ratio,
             args.strength, args.seed, args.model, args.reference)
