# Seer 🔦

**Local AI image descriptions for screen readers. No API key. No cloud. Fully private.**

Seer is a browser extension that automatically describes images without alt text using a local AI model (PaliGemma2). Every image is processed on your own computer — nothing is ever sent to a server.

---

## Who is this for?

People who use screen readers (NVDA, JAWS, VoiceOver) and encounter images on the web that have no description. Most websites don't write alt text. Seer fills that gap, silently and automatically.

---

## How it works

```
[Webpage image without alt text]
        ↓
[Seer Extension detects it]
        ↓
[Sends image to local Seer daemon]
        ↓
[PaliGemma2 AI describes the image]
        ↓
[Screen reader announces: "Image: a golden retriever running on a beach"]
```

No internet required after setup. No account. No subscription.

---

## Setup (2 steps)

### Step 1: Start the Seer daemon

```bash
# Install dependencies
pip install fastapi uvicorn

# Start (replace paths with your model locations)
python3 daemon/server.py \
    --model pali2-mix-Q4_K_M.gguf \
    --mmproj pali2-mix-mmproj.gguf \
    --llama-cli /path/to/llama-mtmd-cli
```

The daemon listens on `http://127.0.0.1:11435`.

### Step 2: Install the extension

1. Chrome → `chrome://extensions` → Enable **Developer mode**
2. **Load unpacked** → select the `extension/` folder

---

## Models

Uses **PaliGemma2-3b-mix-224** (Google) — 3B vision-language model for image description, OCR, and VQA.

| File | Size |
|---|---|
| `pali2-mix-Q4_K_M.gguf` | ~1.6 GB |
| `pali2-mix-mmproj.gguf` | ~833 MB |

Requires ~3 GB RAM. No GPU needed.

---

## Privacy

All processing is local. Nothing leaves your computer.

---

## Why we built this

Most AI image description tools need a cloud API — meaning you pay per image, your photos go to someone else's server, and it doesn't work offline.

We believe accessibility tools should be free, private, and work for everyone — including people in low-resource environments.

---

## License

Apache 2.0 — Built by [Recursia Lab](https://github.com/recursia-lab)
