import json
from pathlib import Path

def load_config(path="config.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def ensure_dir(p):
    Path(p).mkdir(parents=True, exist_ok=True)