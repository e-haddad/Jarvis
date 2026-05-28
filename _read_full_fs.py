with open("filesystem.py", "r") as f:
    content = f.read()
# Print from BACKUP_DIR onward
idx = content.find("BACKUP_DIR")
print(content[idx:])
