with open("/Users/edwardhaddad/Desktop/Projects/Jarvis/agents.py", "r") as f:
    content = f.read()
# Print the tool definitions section
start = content.find("CAREER_TOOLS")
print(content[start:start+14000])
