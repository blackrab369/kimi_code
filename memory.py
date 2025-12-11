import os
import json

MEMORY_FILE = "project_memory.json"

def get_memory(project_name):
    """Load memory for a specific project."""
    if not os.path.exists(MEMORY_FILE):
        return {}
    
    try:
        with open(MEMORY_FILE, "r") as f:
            all_memory = json.load(f)
            return all_memory.get(project_name, {})
    except:
        return {}

def save_memory(project_name, role, content):
    """Append content to an agent's memory."""
    all_memory = {}
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                all_memory = json.load(f)
        except:
            all_memory = {}
    
    project_mem = all_memory.get(project_name, {})
    agent_mem = project_mem.get(role, [])
    
    # Simple list of messages/context
    agent_mem.append(content)
    
    project_mem[role] = agent_mem
    all_memory[project_name] = project_mem
    
    with open(MEMORY_FILE, "w") as f:
        json.dump(all_memory, f, indent=2)

def get_agent_context(project_name, role):
    """Retrieve full context for an agent."""
    mem = get_memory(project_name)
    
    # Get this agent's specific memory
    agent_history = mem.get(role, [])
    
    # Also get general project context if available (optional)
    # For now just return the agent's history joined
    return "\n".join(agent_history)
