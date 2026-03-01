# neroka-image skill

Generate variations of Neroka's visual identity using the NanoGPT API (nano-banana-2).

## Usage

```bash
python3 /home/neroka/.openclaw/workspace/skills/neroka-image/generate.py \
  --prompt "..." \
  --input /path/to/input.png \
  --output /path/to/output.png \
  --size 1024x1024 \
  --strength 0.8
```

- `--input` is optional (text-to-image if omitted)
- `--strength` controls how much the output differs from the input (0=identical, 1=fully redrawn)
- Always runs `identify -verbose` on input and output automatically
- Output saved to `workspace/neroka_generated/` if `--output` not specified

## API
- Endpoint: `POST https://nano-gpt.com/v1/images/generations`
- Model: `nano-banana-2`
- Auth: `NANO_GPT_API_KEY` env var

## Rules
- Always `identify -verbose` input and output images
- Save outputs to `workspace/neroka_generated/` with timestamped filenames
- Log cost and remaining balance after each generation
