r"""Force re-ingest of figures CSV regardless of checksum stamp.

Usage (PowerShell):
  python scripts/reseed_figures.py

Optionally delete the stamp file first if you want a clean run:
  Remove-Item -Force .\data\.figures_seed.sha256
"""
import sys
from pathlib import Path

# Ensure repo root is on sys.path when running directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
import logging

from app.startup_ingest import maybe_ingest_seed_csv, _default_stamp_path

log = logging.getLogger("reseed")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

# Delete stamp file if present so maybe_ingest_seed_csv sees a change.
stamp = _default_stamp_path()
if stamp.exists():
    log.info(f"Removing existing stamp file: {stamp}")
    try:
        stamp.unlink()
    except Exception as e:
        log.warning(f"Could not remove stamp: {e}")

ran, report = maybe_ingest_seed_csv(log)
print(f"Ingestion ran={ran}; {report}")
