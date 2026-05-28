with open("think.py", "r") as f:
    content = f.read()
idx = content.find("TOOLS = [")
print(content[idx:idx+12000])
