#!/usr/bin/env bash
# Seer daemon installer for Linux / macOS
set -e

echo ""
echo " Seer — Local AI Image Descriptions"
echo " ===================================="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo " [ERROR] python3 not found. Install it first:"
    echo "   macOS:  brew install python"
    echo "   Ubuntu: sudo apt install python3 python3-pip"
    exit 1
fi

echo " [1/3] Installing Python dependencies..."
pip3 install fastapi uvicorn --quiet

# Check Ollama
if ! command -v ollama &>/dev/null; then
    echo ""
    echo " [2/3] Ollama not found. Install with:"
    echo "   curl -fsSL https://ollama.com/install.sh | sh"
    echo " Then re-run this script."
    exit 1
fi

# Start Ollama in background if not running
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo " Starting Ollama service..."
    ollama serve &>/dev/null &
    sleep 3
fi

echo " [2/3] Pulling vision model (moondream ~1.7 GB)..."
ollama pull moondream

# Create launcher script
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cat > "$SCRIPT_DIR/seer-start.sh" <<EOF
#!/usr/bin/env bash
# Start Seer daemon (Ollama backend, moondream model)
# To use PaliGemma2 after our llama.cpp PR merges:
#   ollama pull paligemma2
#   change --model moondream to --model paligemma2
python3 "$SCRIPT_DIR/server.py" ollama --model moondream
EOF
chmod +x "$SCRIPT_DIR/seer-start.sh"

echo " [3/3] Created: $SCRIPT_DIR/seer-start.sh"
echo ""
echo " Done! Start Seer with:"
echo "   $SCRIPT_DIR/seer-start.sh"
echo ""
echo " To start automatically on login (macOS):"
echo "   Add seer-start.sh to System Settings → General → Login Items"
echo ""
