"""Fixed project launcher; the host UI never imports LangGraph or parser engines."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from local_ai_appliance.windows_desktop import main

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--evaluation',action='store_true',help='Explicit administrator-enrolled synthetic candidate only')
    args=parser.parse_args()
    raise SystemExit(main(ROOT,evaluation=args.evaluation))
