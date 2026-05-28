import re
from pathlib import Path

path = Path.home() / "Desktop" / "Projects" / "Jarvis" / "think.py"
content = path.read_text(encoding="utf-8")

# Find all max_tokens occurrences with context
for m in re.finditer(r'max_tokens\s*=\s*\d+', content):
    start = max(0, m.start() - 100)
    end = min(len(content), m.end() + 100)
    print(f"--- pos {m.start()} ---")
    print(repr(content[start:end]))
    print()
