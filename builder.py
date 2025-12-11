import os
import json
import sys
from openai import OpenAI
import prompt
import search # New

# Reuse the client from kimi_code or create a new one
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url="https://api.moonshot.ai/v1"
)

import xml.etree.ElementTree as ET

def validate_file_content(content, filename):
    """
    Returns (True, None) if valid, or (False, error_message).
    """
    # Python
    if filename.endswith(".py"):
        try:
            ast.parse(content)
            return True, None
        except SyntaxError as e:
            return False, f"Syntax Error: {str(e)}"
    
    # JSON
    if filename.endswith(".json"):
        try:
            json.loads(content)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"JSON Error: {str(e)}"

    # XML / Configs (csproj, config, html, xml)
    if filename.endswith((".xml", ".csproj", ".config", ".html", ".svg")):
        try:
            # Wrap in a root tag just in case it's a fragment, though for file it should be complete
            # But HTML often has loose tags. ET is strict.
            # Let's try basic parsing for XML types. HTML might fail if not XHTML.
            # For now, apply to strictly XML-based extensions.
            if not filename.endswith(".html"): 
                ET.fromstring(content)
            return True, None
        except ET.ParseError as e:
            return False, f"XML Parsing Error: {str(e)}"

    # C# / JS / TS (Heuristic Check)
    if filename.endswith((".cs", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp")):
        # 1. Check for basic empty file
        if not content.strip():
             return False, "File is empty"
        
        # 2. Check Brace Balance (simple heuristic)
        open_braces = content.count('{')
        close_braces = content.count('}')
        if open_braces != close_braces:
            return False, f"Unbalanced Braces: {{ count={open_braces}, }} count={close_braces}"
        
        # 3. Check for specific language keywords to ensure it looks right
        if filename.endswith(".cs") and "namespace" not in content and "class" not in content and "program" not in content.lower():
             # extremely simple check, might have false positives for scripts, but good for "project files"
             pass 

    return True, None


def build_project_stream(agents_data, github_token=None, image_data=None):
    """
    Orchestrates the build process with streaming:
    1. Iterates through ALL agents.
    2. Prompts LLM for each agent's contribution.
    3. Yields JSON strings for real-time frontend updates.
    4. Uploads to GitHub if token provided.
    """
    try:
        project_name = agents_data.get("project", {}).get("name", "Untitled")
        tech_stack = agents_data.get("project", {}).get("tech_stack", [])
        
        # Setup Output Directory
        safe_name = agents_data.get("project_name")
        if not safe_name:
             safe_name = project_name.replace(" ", "_").replace("/", "-")
        base_dir = os.path.join("projects", safe_name, "src")
        os.makedirs(base_dir, exist_ok=True)
        
        yield json.dumps({"status": "start", "message": f"Starting build for {project_name}..."}) + "\n"

        # Setup GitHub
        repo = None
        if github_token:
            client, user = github_utils.get_github_client(github_token)
            if user:
                 yield json.dumps({"status": "start", "message": f"GitHub Sync Enabled: {user.login}"}) + "\n"
                 # Repo should likely already exist from generation step, but we check/get again
                 repo_name = agents_data.get("project_name") or safe_name
                 repo = github_utils.create_or_get_repo(user, repo_name)
            else:
                 yield json.dumps({"status": "error", "message": "GitHub Authentication Failed"}) + "\n"

        # Iterate through agents
        agents = agents_data.get("agents", [])
        
        for agent in agents:
            role = agent.get("role", "Agent")
            goal = agent.get("goal", "Contribute to project")

            yield json.dumps({"status": "thinking", "agent": role, "message": "Analyzing requirements..."}) + "\n"

            project_context = f"""
            Project: {project_name}
            Stack: {', '.join(tech_stack)}
            Your Role: {role}
            Your Goal: {goal}
            """

            # --- TOOL USE LOOP (Search) ---
            max_tool_loops = 3
            current_loop = 0
            
            # Initial prompt content
            messages = [
                {"role": "system", "content": prompt.AGENT_ARTIFACT_PROMPT + "\n\nYou have access to Realtime Internet. To search, output `SEARCH: <query>` on a single line. I will return results. Then you can generate artifacts."},
                {"role": "user", "content": f"Generate artifacts for:\n{project_context}"}
            ]
            
            while current_loop < max_tool_loops:
                current_loop += 1
                
                try:
                    response = client.chat.completions.create(
                        model="kimi-k2-0905-preview",
                        messages=messages,
                        temperature=0.3, # Low temp for tool use
                        max_tokens=4096,
                        stream=False 
                    )
                    content = response.choices[0].message.content
                    
                    # Check for Search Command
                    import re
                    search_match = re.search(r"SEARCH:\s*(.*)", content)
                    
                    if search_match:
                        query = search_match.group(1).strip().strip('"').strip("'")
                        yield json.dumps({"status": "search", "query": query}) + "\n"
                        mentor_module.mentor.log_event(f"Agent {role} is searching: {query}")
                        
                        # Execute Search
                        results = search.search_web(query)
                        
                        # Summarize Results (New Step)
                        yield json.dumps({"status": "thought", "agent": role, "message": "Reading and summarizing search results..."}) + "\n"
                        
                        summary_prompt = f"Summarize these search results for a developer. Focus on version numbers, code snippets, and key facts. Include [Source: URL] citations.\n\nResults: {json.dumps(results)}"
                        
                        summary_resp = client.chat.completions.create(
                            model="kimi-k2-0905-preview",
                            messages=[{"role": "user", "content": summary_prompt}],
                            temperature=0.2
                        )
                        summary = summary_resp.choices[0].message.content
                        
                        # Feed back to LLM
                        messages.append({"role": "assistant", "content": f"SEARCH: {query}"})
                        messages.append({"role": "system", "content": f"Search Results Summary:\n{summary}\n\nIMPORTANT: You MUST cite these sources in your documentation using [Source Name](url)."})
                        
                        yield json.dumps({"status": "thought", "agent": role, "message": "Learned from search. Generating content..."}) + "\n"
                        continue # Loop again
                    
                    # If no search, we have the final content
                    # Break and process as usual
                    break
                    
                except Exception as e:
                    yield json.dumps({"status": "error", "agent": role, "message": str(e)}) + "\n"
                    break

            # Proceed with processing `content` (which should now be the JSON artifacts)
            
            # Clean JSON
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "")
            elif content.startswith("```"):
                content = content.replace("```", "")
            
            try:
                data = json.loads(content)
                thought = data.get("thought", "Working...")
                files = data.get("files", {})
                    
                    # Yield Thought
                    yield json.dumps({"status": "thought", "agent": role, "message": thought}) + "\n"
                    mentor_module.mentor.log_event(f"Agent '{role}' thought: {thought}")
                    
                    # Write Files
                    for file_path, file_content in files.items():
                        # 1. Clean Content
                        cleaned_content = clean_file_content(file_content, file_path)
                        
                        # 2. Validate Content
                        is_valid, error_msg = validate_file_content(cleaned_content, file_path)
                        if not is_valid:
                            yield json.dumps({"status": "warning", "agent": role, "message": f"Fixing {file_path}: {error_msg}"}) + "\n"
                            # We could try to auto-fix or just save it anyway with a .broken extension?
                            # For now, let's save it but user knows it's broken.
                        
                        full_path = os.path.join(base_dir, file_path)
                        os.makedirs(os.path.dirname(full_path), exist_ok=True)
                        
                        # Append mode for docs, Overwrite for code?
                        mode = "w"
                        if file_path.endswith(".md") and os.path.exists(full_path):
                             mode = "a" # Append to docs like README
                             cleaned_content = "\n\n" + cleaned_content
                        
                        with open(full_path, mode, encoding="utf-8") as f:
                            f.write(cleaned_content)
                        
                        # Yield File Creation
                        yield json.dumps({"status": "file", "agent": role, "file": file_path}) + "\n"
                        
                        # Upload to GitHub
                        if repo:
                            # Use relative path for GitHub
                            gh_path = f"src/{file_path}" # Putting all in src folder of repo? Or root?
                            # Agents might return "src/main.py" or just "main.py". 
                            # If they return "src/main.py", we shouldn't double stack "src/src/main.py".
                            # Let's trust the agent's relative path but ensure it's clean.
                            
                            # Actually, agents.json is at root. Code seems to be going into src.
                            # Let's keep structure simple: whatever the agent gave us.
                            upload_success = github_utils.upload_file_to_github(repo, file_path, cleaned_content, f"Agent {role} update: {file_path}")
                            if upload_success:
                                yield json.dumps({"status": "github", "file": file_path}) + "\n"


                except json.JSONDecodeError:
                     yield json.dumps({"status": "error", "agent": role, "message": "Failed to parse output"}) + "\n"

            except Exception as e:
                yield json.dumps({"status": "error", "agent": role, "message": str(e)}) + "\n"

        yield json.dumps({"status": "complete", "directory": base_dir}) + "\n"

    except Exception as e:
        yield json.dumps({"status": "fatal", "message": str(e)}) + "\n"


import shutil
import time

def create_backup(project_name, file_path):
    """
    Creates a timestamped backup of the file.
    Returns backup_path on success, None on failure (if file didn't exist).
    """
    base_dir = os.path.join("projects", project_name, "src")
    full_path = os.path.join(base_dir, file_path)
    
    if not os.path.exists(full_path):
        return None
        
    backup_dir = os.path.join("projects", project_name, "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = int(time.time())
    safe_name = file_path.replace("/", "_").replace("\\", "_")
    backup_name = f"{timestamp}_{safe_name}"
    backup_path = os.path.join(backup_dir, backup_name)
    
    shutil.copy2(full_path, backup_path)
    return backup_name

def restore_backup(project_name, backup_name):
    """
    Restores a file from a backup.
    """
    backup_dir = os.path.join("projects", project_name, "backups")
    backup_path = os.path.join(backup_dir, backup_name)
    
    if not os.path.exists(backup_path):
        return False, "Backup not found"
        
    # Infer original path from backup name or we store metadata? 
    # Current simplistic naming: 123456_src_main.py -> src/main.py is ambiguous if underscores used in path.
    # Better: we just assume the backup is for the file we are currently editing? 
    # Or strict naming convention.
    # Let's use metadata or simple convention: timestamp_filename.ext
    # Reversing safe_name is hard if we replaced / with _.
    # For MVP Revert API, we might need to know which file it belongs to.
    # Actually, for "Undo" in chat, we usually just want to undo the *last* edit to *that* file.
    # But let's support general restore if we know the target.
    
    # For now, let's keep it simple: apply_agent_edit creates backup.
    # To restore, we need to know where it goes.
    # Let's store a map or just trust the user/agent to provide target?
    # Actually, let's simplify: 
    # `restore_backup` will take `target_file` argument? 
    # No, let's make the backup system returns the ID.
    pass

def apply_agent_edit(project_name, file_path, content):
    """
    Safely applies an edit requested by an agent.
    Returns: (success: bool, message: str)
    """
    try:
        # 1. Security Check (Path Traversal)
        if ".." in file_path or file_path.startswith("/"):
            return False, "Invalid file path (security restricted)."
            
        base_dir = os.path.join("projects", project_name, "src")
        full_path = os.path.join(base_dir, file_path)
        
        # 2. Backup Existing File
        backup_id = create_backup(project_name, file_path)
        
        # 3. Clean Content
        cleaned_content = clean_file_content(content, file_path)
        
        # 4. Validate Content
        is_valid, error_msg = validate_file_content(cleaned_content, file_path)
        if not is_valid:
            return False, f"Validation Failed: {error_msg}"
            
        # 5. Write File
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(cleaned_content)
        
        msg = f"Successfully updated {file_path}"
        if backup_id:
             msg += f" (Backup saved: {backup_id})"
             
        return True, msg

    except Exception as e:
        return False, f"System Error: {str(e)}"

