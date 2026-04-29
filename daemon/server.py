"""
Seer daemon — local AI image description server for screen readers.

Supports two backends:
  --backend llama-cli   Uses llama-mtmd-cli binary (PaliGemma2 GGUF, fastest)
  --backend ollama      Uses Ollama HTTP API (llava / moondream / paligemma2)

API:
    POST /describe   {"image_url": "..."} or {"image_b64": "..."}
    GET  /health
"""

import argparse
import base64
import json
import subprocess
import tempfile
import time
import os
import urllib.request
import urllib.error
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Seer", description="Local AI image descriptions for screen readers")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

cfg = {}

# Models that need raw prompt (no chat template) — PaliGemma family
_PALIGEMMA_NAMES = {"paligemma", "paligemma2", "pali2"}


class DescribeRequest(BaseModel):
    image_url: str | None = None
    image_b64: str | None = None
    task: str = "caption"
    question: str | None = None
    lang: str = "en"


class DescribeResponse(BaseModel):
    description: str
    time_ms: int
    model: str


def _build_prompt(task: str, question: str | None, lang: str) -> str:
    if task == "vqa" and question:
        return f"answer {lang} {question}\n"
    return f"caption {lang}\n"


def _fetch_image(url: str, dest: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "Seer/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            with open(dest, "wb") as f:
                f.write(r.read())
    except urllib.error.URLError as e:
        raise HTTPException(400, f"Failed to fetch image: {e}")


def _get_image_b64(tmp_path: str) -> str:
    with open(tmp_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _run_llama_cli(tmp_path: str, prompt: str) -> str:
    result = subprocess.run(
        [
            cfg["llama_cli"],
            "-m", cfg["model"],
            "--mmproj", cfg["mmproj"],
            "--image", tmp_path,
            "-p", prompt,
            "-n", "48",
            "--repeat-penalty", "1.3",
            "--no-warmup",
            "-t", str(cfg.get("threads", 4)),
        ],
        capture_output=True, text=True, timeout=180,
    )
    text = result.stdout.strip()
    if not text:
        raise HTTPException(500, f"llama-cli returned no output. stderr: {result.stderr[-300:]}")
    return text


def _run_ollama(tmp_path: str, prompt: str) -> str:
    model = cfg["ollama_model"]
    is_paligemma = any(p in model.lower() for p in _PALIGEMMA_NAMES)

    payload = {
        "model": model,
        "prompt": prompt,
        "images": [_get_image_b64(tmp_path)],
        "stream": False,
    }
    # PaliGemma2 needs raw mode to bypass Ollama's chat template
    if is_paligemma:
        payload["raw"] = True

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{cfg['ollama_url']}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            resp = json.loads(r.read())
    except urllib.error.URLError as e:
        raise HTTPException(502, f"Ollama unreachable: {e}")

    text = resp.get("response", "").strip()
    if not text:
        raise HTTPException(500, f"Ollama returned empty response")
    return text


@app.get("/health")
def health():
    backend = cfg.get("backend", "llama-cli")
    if backend == "ollama":
        return {"status": "ok", "model": cfg.get("ollama_model", ""), "backend": "ollama"}
    return {
        "status": "ok",
        "model": Path(cfg.get("model", "")).name,
        "backend": "llama-cli",
    }


@app.post("/describe", response_model=DescribeResponse)
def describe(req: DescribeRequest):
    if not req.image_url and not req.image_b64:
        raise HTTPException(400, "Provide image_url or image_b64")

    suffix = ".jpg"
    if req.image_url:
        ext = os.path.splitext(req.image_url.split("?")[0])[-1].lower()
        if ext in (".png", ".gif", ".webp", ".bmp"):
            suffix = ext

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        tmp_path = f.name
        if req.image_b64:
            try:
                f.write(base64.b64decode(req.image_b64))
            except Exception:
                raise HTTPException(400, "Invalid base64 image data")
        else:
            f.close()
            _fetch_image(req.image_url, tmp_path)

    try:
        prompt = _build_prompt(req.task, req.question, req.lang)
        t0 = time.time()

        if cfg.get("backend") == "ollama":
            description = _run_ollama(tmp_path, prompt)
            model_name = cfg.get("ollama_model", "ollama")
        else:
            description = _run_llama_cli(tmp_path, prompt)
            model_name = Path(cfg["model"]).name

        elapsed = int((time.time() - t0) * 1000)
        return DescribeResponse(description=description, time_ms=elapsed, model=model_name)

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Seer daemon — local AI image descriptions")
    sub = parser.add_subparsers(dest="backend")

    # llama-cli backend (PaliGemma2 GGUF)
    p_llama = sub.add_parser("llama-cli", help="Use llama-mtmd-cli binary")
    p_llama.add_argument("--model", required=True, help="Path to PaliGemma2 text GGUF")
    p_llama.add_argument("--mmproj", required=True, help="Path to PaliGemma2 mmproj GGUF")
    p_llama.add_argument("--llama-cli", default="llama-mtmd-cli",
                         help="Path to llama-mtmd-cli binary")
    p_llama.add_argument("--threads", type=int, default=4)

    # Ollama backend (llava / moondream / paligemma2)
    p_ollama = sub.add_parser("ollama", help="Use Ollama HTTP API")
    p_ollama.add_argument("--model", default="moondream",
                          help="Ollama model name (e.g. moondream, llava, paligemma2)")
    p_ollama.add_argument("--ollama-url", default="http://127.0.0.1:11434")

    for p in (p_llama, p_ollama):
        p.add_argument("--host", default="127.0.0.1")
        p.add_argument("--port", type=int, default=11435)

    args = parser.parse_args()

    if args.backend is None:
        parser.print_help()
        return

    cfg["backend"] = args.backend

    if args.backend == "llama-cli":
        cfg["model"] = args.model
        cfg["mmproj"] = args.mmproj
        cfg["llama_cli"] = args.llama_cli
        cfg["threads"] = args.threads
        print(f"Seer daemon  backend=llama-cli  model={Path(args.model).name}")
    else:
        cfg["ollama_model"] = args.model
        cfg["ollama_url"] = args.ollama_url
        print(f"Seer daemon  backend=ollama  model={args.model}  url={args.ollama_url}")

    print(f"  listening on http://{args.host}:{args.port}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
