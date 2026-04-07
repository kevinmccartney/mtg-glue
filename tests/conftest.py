import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PROJECTS = _ROOT / "projects"
if str(_PROJECTS) not in sys.path:
    sys.path.insert(0, str(_PROJECTS))
