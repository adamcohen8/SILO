"""Fixed project launcher; the host UI never imports LangGraph or parser engines."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.windows_desktop import main

if __name__ == '__main__':
    raise SystemExit(main(ROOT))
