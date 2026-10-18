#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Thread performance optimizations for Python 3.14 on macOS/Linux
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

echo "==============================================================="
echo "   KSHAMATA-SETU (SIH26135) — FAST MVP LAUNCHER"
echo "   Team HexaCore | Government of Maharashtra Showcase"
echo "==============================================================="

# Check virtualenv
if [ ! -d "venv" ]; then
    echo "[*] Creating Python virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

# Seed DB if not present
if [ ! -f "kshamata_setu.db" ]; then
    echo "[*] Initializing and seeding synthetic database..."
    ./venv/bin/python seed_data.py
fi

echo ""
echo "==============================================================="
echo "  ⚡ MVP READY TO DEMO:"
echo "  -> Live Simulator     : http://127.0.0.1:8000/"
echo "  -> Analytics Dashboard: http://127.0.0.1:8000/dashboard"
echo "  -> Integration Center : http://127.0.0.1:8000/integrations-ui"
echo "  -> API Documentation  : http://127.0.0.1:8000/docs"
echo "==============================================================="
echo ""

exec ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
