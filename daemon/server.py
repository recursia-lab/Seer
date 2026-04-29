"""
Seer daemon — local AI image description server for screen readers.
Wraps llama-mtmd-cli (llama.cpp + PaliGemma2) behind a simple HTTP API.

Usage:
    python server.py --model pali2-text.gguf --mmproj pali2-mmproj.gguf

API:
    POST /describe   {"image_url": "..."} or {"image_b64": "..."}
    GET  /health
"""

import argparse
import base64
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

# Allow browser extension to call localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

cfg = {}


class DescribeRequest(BaseModel):
    image_url: str | None = None
    image_b64: str | None = None
    task: str = "caption"       # "caption" or "vqa"
    question: str | None = None # used when task="vqa"
    lang: str = "en"


class DescribeResponse(BaseModel):
    description: str
    time_ms: int
    model: str


def _build_prompt(task: str, question: str | None, lang: str) -> str:
    # PaliGemma2 requires task prefix + language + \n at the end
    # Correct format: "caption en\n" or "answer en What is this?\n"
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


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": Path(cfg.get("model", "")).name,
        "mmproj": Path(cfg.get("mmproj", "")).name,
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
            capture_output=True, text=True, timeout=180
        )
        elapsed = int((time.time() - t0) * 1000)

        description = result.stdout.strip()
        if not description:
            stderr_tail = result.stderr[-300:] if result.stderr else ""
            raise HTTPException(500, f"Model returned no output. stderr: {stderr_tail}")

        return DescribeResponse(
            description=description,
            time_ms=elapsed,
            model=Path(cfg["model"]).name,
        )

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def main():
    parser = argparse.ArgumentParser(description="Seer daemon — local AI image descriptions")
    parser.add_argument("--model", required=True, help="Path to PaliGemma2 text GGUF")
    parser.add_argument("--mmproj", required=True, help="Path to PaliGemma2 mmproj GGUF")
    parser.add_argument("--llama-cli", default="llama-mtmd-cli",
                        help="Path to llama-mtmd-cli binary (default: llama-mtmd-cli in PATH)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11435)
    parser.add_argument("--threads", type=int, default=4, help="CPU threads for inference")
    args = parser.parse_args()

    cfg["model"] = args.model
    cfg["mmproj"] = args.mmproj
    cfg["llama_cli"] = args.llama_cli
    cfg["threads"] = args.threads

    print(f"Seer daemon v0.1.0")
    print(f"  model:   {Path(args.model).name}")
    print(f"  mmproj:  {Path(args.mmproj).name}")
    print(f"  listen:  http://{args.host}:{args.port}")
    print(f"  threads: {args.threads}")

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
