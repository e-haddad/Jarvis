with open("filesystem.py", "r") as f:
    content = f.read()
idx = content.find("def move_file")
print(content[idx:])
