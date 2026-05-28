
import re

path = "/Users/edwardhaddad/Desktop/Projects/Jarvis/think.py"

with open(path, "r") as f:
    content = f.read()

# Find all max_tokens occurrences
matches = [(m.start(), m.group()) for m in re.finditer(r'max_tokens\s*=\s*\d+', content)]
print("Found:")
for pos, m in matches:
    print(f"  {m} at char {pos}")

# Replace only Sonnet-related max_tokens (8192)
new_content = re.sub(r'(max_tokens\s*=\s*)8192', r'\g<1>16000', content)

changed = content != new_content
print(f"\nChanged: {changed}")

if changed:
    with open(path, "w") as f:
        f.write(new_content)
    print("Written.")
