
path = "/Users/edwardhaddad/Desktop/Projects/Jarvis/think.py"

with open(path, "r") as f:
    lines = f.readlines()

# Print lines containing 'max_tokens' or 'SONNET' near each other
for i, line in enumerate(lines):
    if 'max_tokens' in line or ('SONNET' in line and 'max_tokens' in ''.join(lines[max(0,i-3):i+4])):
        print(f"{i+1:4}: {line}", end="")
