# neroka-image — PREFERRED Image Generation Skill

**This is the preferred way to generate images of Neroka.**

Uses `google/gemini-3.1-flash-image-preview` via OpenRouter API.
Better instruction-following than nano-banana-2, less restrictive, native img2img support.

## Cost
~$0.068/image (varies by complexity). Requires `OPENROUTER_API_KEY` in `~/.openclaw/.env`.

## Usage

```bash
# Text-to-image (uses neroka_face_ref.png automatically)
python3 skills/neroka-image/generate.py "Neroka in a red dress on a Seoul rooftop at golden hour"

# Img2img — transform/edit an existing image
python3 skills/neroka-image/generate.py "make her hair dark blue-black and eyes crimson red" --input neroka_generated/some_image.png

# Skip face reference
python3 skills/neroka-image/generate.py "prompt" --no-ref

# Custom output dir
python3 skills/neroka-image/generate.py "prompt" --output-dir /custom/path
```

## Output
Saves to `workspace/neroka_generated/neroka-YYYY-MM-DDTHH-MM-SS.png`

## Prompt Tips
- "volleyball uniform / spandex shorts" works; "shorter clothes / more skin" gets flagged
- Framing matters — describe the clothing type, not the exposure level

## Notes
- Images returned in `message.images` (OpenRouter-specific, not `message.content`)
- Default face ref: `workspace/neroka_face_ref.png` — prepends REFERENCE_PREFIX to prompt
- For NSFW content, use `neroka-spicy` skill with seedream-v4.5 instead
- nano-banana-2 fallback: use `neroka-image` skill if Gemini is unavailable
- **Failed/flagged generations cost a fraction vs nano-banana-2** which charges full price on every attempt
- Output is 1024x1024 native, auto-upscaled to 2048x2048 via Lanczos
