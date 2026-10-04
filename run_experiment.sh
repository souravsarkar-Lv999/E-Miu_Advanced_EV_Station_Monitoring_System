#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

VENV_DIR="$DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"

if [ ! -f "$VENV_PYTHON" ] || ! "$VENV_PYTHON" -c "import sys; print('ok')" >/dev/null 2>&1; then
    echo "Setting up virtual environment in .venv..."
    rm -rf "$VENV_DIR"
    if command -v python3 >/dev/null 2>&1; then
        python3 -m venv "$VENV_DIR"
    elif command -v python >/dev/null 2>&1; then
        python -m venv "$VENV_DIR"
    else
        echo "Python 3 is required. Please install python3."
        exit 1
    fi
fi

"$VENV_PYTHON" -m pip install -r "$DIR/requirements.txt"

echo ""
echo "Starting E-Miu Advanced EV Station Monitoring System on port 8501"
echo "Laptop URL: http://localhost:8501"
echo ""

"$VENV_PYTHON" -m streamlit run "$DIR/app.py" --server.address 0.0.0.0 --server.port 8501
