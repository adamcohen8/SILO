"""Trusted source entry point; never load code from the payload bundle."""
from pathlib import Path
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from local_ai_appliance.installation import main
if __name__ == '__main__': raise SystemExit(main())
