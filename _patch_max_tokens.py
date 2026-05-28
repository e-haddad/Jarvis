import re
from pathlib import Path

path = Path.home() / "Desktop" / "Projects" / "Jarvis" / "think.py"
content = path.read_text(encoding="utf-8")

# Find all occurrences of max_tokens
matches = [(m.start(), m.group()) for m in re.finditer(r'max_tokens\s*=\s*\d+', content)]
print("Found:", matches)

# Replace 8192 with 16000
new_content = re.sub(r'(max_tokens\s*=\s*)8192', r'\g<1>16000', content)

changed = content != new_content
print("Changed:", changed)

if changed:
    path.write_text(new_content, encoding="utf-8")
    print("Written.")
    # Verify
    updated = [(m.start(), m.group()) for m in re.finditer(r'max_tokens\s*=\s*\d+', new_content)]
    print("After patch:", updated)
