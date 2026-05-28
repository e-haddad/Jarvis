
import re

path = "/Users/edwardhaddad/Desktop/Projects/Jarvis/think.py"

with open(path, "r") as f:
    content = f.read()

# Replace the three ternary patterns for Sonnet max_tokens
# Pattern: max_tokens = 400 if model == HAIKU else 800
#      and: max_tokens = 400 if model == HAIKU else 1000
new_content = re.sub(
    r'(max_tokens\s*=\s*400\s+if\s+model\s*==\s*HAIKU\s+else\s+)(800|1000)',
    r'\g<1>16000',
    content
)

changed = content != new_content
print(f"Changed: {changed}")

# Show what changed
for old, new in [("else 800", "else 16000"), ("else 1000", "else 16000")]:
    count = content.count(old.replace("else ", "else "))
    print(f"  '{old}' occurrences replaced: {content.count(old)}")

if changed:
    with open(path, "w") as f:
        f.write(new_content)
    print("Written.")
