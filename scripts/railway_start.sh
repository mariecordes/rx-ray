#!/usr/bin/env sh
set -eu

PORT="${PORT:-8000}"

echo "Starting rx-ray on Railway"
echo "Working directory: $(pwd)"
python --version

python - <<'PY'
from pathlib import Path
import importlib
import sys

print(f"Python executable: {sys.executable}")

for module_name in ("uvicorn", "fastapi", "pandas", "pyarrow", "requests"):
    module = importlib.import_module(module_name)
    version = getattr(module, "__version__", "installed")
    print(f"{module_name}: {version}")

for path in (
    Path("apps/api/main.py"),
    Path("conf/base/parameters.yml"),
    Path("conf/base/prompts.yml"),
    Path("data/01_raw/rxnorm_prescribable"),
):
    print(f"{path}: exists={path.exists()}")
PY

exec python -m uvicorn apps.api.main:app --host 0.0.0.0 --port "${PORT}"
