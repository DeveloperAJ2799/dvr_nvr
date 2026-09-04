#!/usr/bin/env bash
# NYAYA Forensics - end-to-end smoke test for the Python sidecar.
# Creates a synthetic .dav (Dahua DHAV magic) and exercises every module.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

echo "=== 1. py_compile all modules ==="
python -m py_compile core/*.py plugins/*.py ai/*.py report/*.py sidecar.py && echo OK

echo "=== 2. vendor detection on synthetic .dav ==="
python core/device_detect.py --file test_data/sample.dav

echo "=== 3. Dahua BCD -> IST ==="
python core/timestamps.py --dahua-bcd 18260615103000

echo "=== 4. Hikvision epoch -> IST ==="
python core/timestamps.py --hik-epoch 1782924600

echo "=== 5. streaming acquisition (read-only) ==="
python core/acquisition.py --image test_data/sample.dav --out test_data/out

echo "=== 6. sidecar dispatcher ==="
python sidecar.py detect --file test_data/sample.dav

echo "=== 7. recovery carving ==="
python plugins/recovery.py --image test_data/sample.dav --out test_data/recovered --max 2

echo "=== 8. dahua/hikvision wrapper (expect 'tool missing' - no parser installed) ==="
python plugins/dahua_wrapper.py --image test_data/sample.dav --out test_data/dahua_out || true
python plugins/hikvision_wrapper.py --image test_data/sample.dav --out test_data/hik_out || true

echo "=== 9. decoder (expect 'ffmpeg not found' if not installed) ==="
python plugins/decoder.py --input test_data/sample.dav --out test_data/decoded.mp4 || true

echo "=== 10. AI analytics (expect 'ultralytics not installed' if not installed) ==="
python ai/analytics.py --video test_data/sample.dav --mode motion || true
python ai/analytics.py --video test_data/sample.dav --mode object || true

echo "=== ALL SMOKE TESTS DONE ==="