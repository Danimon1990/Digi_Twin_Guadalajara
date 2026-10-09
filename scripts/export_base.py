"""Backward-compatible entry point for the layered OpenUSD exporter."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("export_layered_usd.py")
SPEC = importlib.util.spec_from_file_location("guadalajara_export_layered_usd", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
main = MODULE.main


if __name__ == "__main__":
    main()
