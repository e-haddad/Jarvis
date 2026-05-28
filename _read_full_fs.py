with open("filesystem.py", "r") as f:
    content = f.read()
# Print from restore_backup onward
idx = content.find("def restore_backup")
print(content[idx:])
