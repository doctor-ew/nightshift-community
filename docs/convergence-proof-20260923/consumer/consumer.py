import json
from pathlib import Path
def transform(value):
    return value * json.loads(Path("current.json").read_text())["multiplier"]
