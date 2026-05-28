import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"=== TOTAL CHARS: {len(content)} ===")
print(content[start:start+10000])
