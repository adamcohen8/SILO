"""Start the shared contained terminal from reviewed source or an installed app."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from local_ai_appliance.terminal_client import main
if __name__=='__main__': raise SystemExit(main(ROOT))
