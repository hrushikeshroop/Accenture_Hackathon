import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controlplane.core.evaluator import ControlPlaneEvaluator  # noqa: E402

if __name__ == "__main__":
    evaluator = ControlPlaneEvaluator()
    print(f"Initialized audit database at {evaluator.settings.db_path}")
