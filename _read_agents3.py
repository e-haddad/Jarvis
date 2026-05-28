with open("/Users/edwardhaddad/Desktop/Projects/Jarvis/agents.py", "r") as f:
    content = f.read()
# Print PROJECTS_TOOLS onward - second half
start = content.find("PROJECTS_TOOLS")
print(content[start+4000:start+14000])
