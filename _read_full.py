import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"=== TOTAL CHARS: {len(content)} ===")
# Print from char 8000 onwards
print(content[8000:])
