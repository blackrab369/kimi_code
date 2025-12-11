import os
from flask import Flask, render_template, request, jsonify, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from werkzeug.utils import secure_filename
from kimi_code import generate_agents
from dotenv import load_dotenv
import github_utils
import re
import os
import json
import bleach
import shutil
import time
from models import db, Project, User, Package, Transaction
import memory
import mentor as mentor_module
from flask import send_file  # Used in export_zip function but not imported
import subprocess  # Used in git routes but not imported at the top
import shlex
from typing import List, Dict, Any
from typing import Optional
from enum import Enum
from dataclasses import dataclass
from typing import List, Set


load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# --- Security Helpers ---
def get_secure_project_path(project_name):
    if not project_name: raise ValueError("Project Name required")
    s_name = secure_filename(project_name)
    base_dir = os.path.abspath("projects")
    target_path = os.path.abspath(os.path.join(base_dir, s_name))
    if not target_path.startswith(base_dir): raise ValueError("Path traversal detected")
    return target_path

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

# --- Git Routes ---
@app.route("/api/git/init", methods=["POST"])
def git_init():
    try:
        data = request.get_json()
        root = get_secure_project_path(data.get("project_name"))
        import subprocess
        subprocess.check_output(["git", "init"], cwd=root)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route("/api/git/status", methods=["GET"])
def git_status():
    try:
        root = get_secure_project_path(request.args.get("project_name"))
        if not os.path.exists(os.path.join(root, ".git")): return jsonify({"code": "NO_REPO"})
        import subprocess
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=root).decode()
        log = subprocess.check_output(["git", "log", "-n", "5", "--pretty=format:%h|%s|%ar"], cwd=root).decode() 
        return jsonify({"status": status, "log": log})
    except: return jsonify({"status": "", "log": ""})

@app.route("/api/git/commit", methods=["POST"])
def git_commit():
    try:
        data = request.get_json()
        root = get_secure_project_path(data.get("project_name"))
        import subprocess
        subprocess.check_output(["git", "add", "."], cwd=root)
        subprocess.check_output(["git", "commit", "-m", data.get("message", "Update")], cwd=root)
        return jsonify({"status": "success"})
    except Exception as e: return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# Security Configuration
# ------------------------------------------------------------------
# Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Secure Headers (Force HTTPS, CSP)
# Note: content_security_policy needs to be carefully tuned for inline scripts/styles if used
csp = {
    'default-src': '\'self\'',
    'script-src': ['\'self\'', '\'unsafe-inline\''], # Allowing inline for our script.js ease, consider moving to nonce in prod
    'style-src': ['\'self\'', '\'unsafe-inline\'', 'https://fonts.googleapis.com'],
    'font-src': ['\'self\'', 'https://fonts.gstatic.com'],
    'img-src': ['\'self\'', 'data:', 'https://via.placeholder.com']
}
talisman = Talisman(app, content_security_policy=csp, force_https=False) # force_https=False for local dev

# ------------------------------------------------------------------
# Database Configuration
# ------------------------------------------------------------------
# Use a default sqlite for easy dev if DATABASE_URL not set, but prefer Postgres
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///local_dev.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# Create tables on startup (simplistic approach for this scale)
with app.app_context():
    db.create_all()


@app.route("/")
def index():
    project_name = request.args.get("project")
    existing_data = None
    
    if project_name:
        # Load project from DB to inject into template (or let JS fetch it)
        # For simplicity, we'll let the frontend fetch it via an API or inject JSON here.
        # Injection is faster for "Resume".
        user_identifier = session.get("github_user", "anonymous")
        # In multi-user env, filter by user. For now, find by name.
        proj = Project.query.filter_by(project_name=project_name).first()
        if proj:
            existing_data = proj.agents_data
            # Ensure project name matches exactly in data
            if existing_data:
                existing_data["project_name"] = proj.project_name

    return render_template("index.html", initial_data=existing_data)

@app.route("/dashboard")
def dashboard():
    # List projects
    # If using authentication, filter by user
    user_identifier = session.get("github_user")
    
    if user_identifier:
        projects = Project.query.filter_by(user_identifier=user_identifier).all()
    else:
        # Fallback for anonymous trial or local dev
        projects = Project.query.all()
        
    return render_template("dashboard.html", projects=projects)

@app.route("/api/project/agents", methods=["GET", "POST"])
def project_agents():
    project_name = request.args.get("project_name")
    
    if request.method == "GET":
        proj = Project.query.filter_by(project_name=project_name).first()
        if proj and proj.agents_data:
            return jsonify(proj.agents_data)
        return jsonify({"error": "Project not found"}), 404
        
    if request.method == "POST":
        data = request.get_json()
        project_name = data.get("project_name")
        agents_data = data.get("agents_data") # The full JSON struct
        
        proj = Project.query.filter_by(project_name=project_name).first()
        if proj:
            proj.agents_data = agents_data
            db.session.commit()
            mentor_module.mentor.log_event(f"User updated Agent Personas for '{project_name}'")
            return jsonify({"status": "updated"})
        return jsonify({"error": "Project not found"}), 404

@app.route("/api/deploy/prepare_vercel", methods=["POST"])
def deploy_vercel():
    data = request.get_json()
    project_name = data.get("project_name")
    
    project_root = os.path.join("projects", project_name)
    if not os.path.exists(project_root):
        return jsonify({"error": "Project not found"}), 404
        
    try:
        # Create vercel.json
        # Assuming static site in 'src' or root? 
        # Our builder uses 'src' for code.
        config = {
            "version": 2,
            "builds": [
                { "src": "src/**", "use": "@vercel/static" }
            ],
            "routes": [
                { "src": "/(.*)", "dest": "/src/$1" }
            ]
        }
        
        with open(os.path.join(project_root, "vercel.json"), "w") as f:
            json.dump(config, f, indent=2)
            
        mentor_module.mentor.log_event(f"Generated Vercel configuration for '{project_name}'")
        
        return jsonify({
            "status": "ready",
            "message": "Configuration generated.",
            "command": "npm i -g vercel && vercel" # CLI instruction
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/deploy/setup_supabase", methods=["POST"])
def deploy_supabase():
    data = request.get_json()
    project_name = data.get("project_name")
    url = data.get("url")
    key = data.get("key")
    
    if not url or not key:
         return jsonify({"error": "Missing credentials"}), 400
         
    project_root = os.path.join("projects", project_name)
    src_dir = os.path.join(project_root, "src")
    
    if not os.path.exists(src_dir):
         os.makedirs(src_dir, exist_ok=True)
         
    try:
        # Generate supabase.js helper
        content = f"""
// Supabase Client Configured by Deployment Center
import {{ createClient }} from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js/+esm'

const supabaseUrl = '{url}'
const supabaseKey = '{key}'

export const supabase = createClient(supabaseUrl, supabaseKey)
console.log("Supabase Client Initialized");
"""
        with open(os.path.join(src_dir, "supabase.js"), "w") as f:
            f.write(content.strip())
            
        mentor_module.mentor.log_event(f"Configured Supabase for '{project_name}'")
        
        return jsonify({
            "status": "configured", 
            "message": "supabase.js created in src/ folder.",
            "usage": "import { supabase } from './supabase.js';"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/export/zip", methods=["GET"])
def export_zip():
    project_name = request.args.get("project_name")
    try:
        project_root = get_secure_project_path(project_name)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
        
    if not os.path.exists(project_root):
        return jsonify({"error": "Project not found"}), 404
        
    try:
        import shutil
        archive_dir = os.path.join("archives")
        os.makedirs(archive_dir, exist_ok=True)
        
        base_name = os.path.join(archive_dir, secure_filename(project_name))
        zip_path = shutil.make_archive(base_name, 'zip', project_root)
        
        mentor_module.mentor.log_event(f"User downloaded source code for '{project_name}'")
        
        return send_file(zip_path, as_attachment=True)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# Auth Routes (GitHub OAuth)
# ------------------------------------------------------------------
from flask import redirect, url_for
import requests

GITHUB_CLIENT_ID = os.getenv('GITHUB_CLIENT_ID')
GITHUB_CLIENT_SECRET = os.getenv('GITHUB_CLIENT_SECRET')

@app.route('/login')
def login():
    if not GITHUB_CLIENT_ID:
        return "GITHUB_CLIENT_ID not configured", 500
    return redirect(f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo,user")

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "No code provided", 400
        
    # Exchange code for token
    token_resp = requests.post(
        'https://github.com/login/oauth/access_token',
        data={
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code
        },
        headers={'Accept': 'application/json'}
    )
    token_json = token_resp.json()
    access_token = token_json.get('access_token')
    
    if not access_token:
        return f"Failed to get token: {token_json}", 400
        
    # Get User Info
    user_resp = requests.get(
        'https://api.github.com/user',
        headers={'Authorization': f'token {access_token}', 'Accept': 'application/json'}
    )
    user_data = user_resp.json()
    username = user_data.get('login')
    
    # Session Management
    session['github_token'] = access_token
    session['github_user'] = username
    
    # Sync User to DB
    user = User.query.get(username)
    if not user:
        user = User(username=username)
        db.session.add(user)
        db.session.commit()
    
    return redirect(url_for('index'))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route("/api/user-status")
def user_status():
    from flask import g
    if not g.user: 
        return jsonify({"is_subscribed": False, "days_left": 0})
        
    return jsonify({
        "is_subscribed": g.user.is_subscribed,
        "days_left": g.user.days_left_in_trial(),
        "username": g.user.username
    })

@app.route("/api/subscribe/create", methods=["POST"])
def create_subscription():
    # In a real app, you call PayPal API to create a Plan/Subscription
    # returning the subscriptionID.
    # For MVP sandbox, we can simulate or create a simple plan ID.
    return jsonify({"plan_id": "P-SIMULATED-PLAN-ID"}) 

@app.route("/api/subscribe/capture", methods=["POST"])
def capture_subscription():
    data = request.get_json()
    sub_id = data.get("subscriptionID")
    
    # Verify with PayPal API in production using PAYPAL_SECRET
    # ... logic ...
    
    # Update DB
    from flask import g
    if g.user:
        g.user.is_subscribed = True
        g.user.subscription_id = sub_id
        g.user.subscription_status = 'active'
        db.session.commit()
        return jsonify({"status": "success"})
    
    return jsonify({"error": "User not found"}), 404


@app.route("/settings/github", methods=["POST"])
@limiter.limit("10 per minute")
def save_github_token():
    data = request.get_json()
    token = data.get("token")
    if token:
        # Sanitize token input just in case
        token = bleach.clean(token)
        
        # verify token
        client, user = github_utils.get_github_client(token)
        if client:
            session["github_token"] = token
            session["github_user"] = user.login
            return jsonify({"status": "success", "username": user.login})
        else:
            return jsonify({"status": "error", "message": "Invalid Token"}), 400
    return jsonify({"status": "error", "message": "No token provided"}), 400

@app.route("/generate", methods=["POST"])
@limiter.limit("5 per minute") 
def generate():
    data = request.get_json()
    raw_idea = data.get("idea")
    
    if not raw_idea:
        return jsonify({"error": "No idea provided"}), 400
    
    # ------------------------------------------------------------------
    # Input Sanitization
    # ------------------------------------------------------------------
    idea = bleach.clean(raw_idea)
    
    try:
        # 1. Generate Agents & Create Local Project
        result = generate_agents(idea)
        
        # ------------------------------------------------------------------
        # Save to Database
        # ------------------------------------------------------------------
        project_name = result.get("project_name", "Untitled")
        user_identifier = session.get("github_user", "anonymous")
        
        new_project = Project(
            user_identifier=user_identifier,
            project_name=project_name,
            idea_prompt=idea,
            agents_data=result
        )
        db.session.add(new_project)
        db.session.commit()
        
        
        # 2. Sync to GitHub if token exists
        github_status = "skipped"
        if "github_token" in session:
            token = session["github_token"]
            client, user = github_utils.get_github_client(token)
            if client and "project_name" in result:
                repo_name = result["project_name"]
                repo = github_utils.create_or_get_repo(user, repo_name)
                
                # Upload agents.json
                local_path = result.get("local_path")
                if local_path and os.path.exists(local_path):
                    with open(local_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    success = github_utils.upload_file_to_github(repo, "agents.json", content)
                    github_status = "success" if success else "failed"
                    result["github_repo_url"] = repo.html_url
        
        result["github_status"] = github_status
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

import builder

@app.route("/build", methods=["POST"])
@limiter.limit("2 per minute")
def build_project_route():
    data = request.get_json()
    agents_data = data.get("agents_data")
    
    if not agents_data:
        return jsonify({"error": "No agents data provided"}), 400

    token = session.get("github_token")

    from flask import Response, stream_with_context
    return Response(
        stream_with_context(builder.build_project_stream(agents_data, github_token=token)),
        mimetype='application/x-ndjson'
    )

import memory

@app.route("/api/revert", methods=["POST"])
def revert_backup():
    # Simplistic revert: Copy backup content back to src
    data = request.get_json()
    project_name = data.get("project_name")
    backup_name = data.get("backup_name")
    target_file = data.get("target_file") # Expected since mapping is hard
    
    if not all([project_name, backup_name, target_file]):
        return jsonify({"error": "Missing fields"}), 400
        
    try:
        backup_path = os.path.join("projects", project_name, "backups", backup_name)
        target_path = os.path.join("projects", project_name, "src", target_file)
        
        if os.path.exists(backup_path):
             import shutil
             shutil.copy2(backup_path, target_path)
 @app.route("/api/save", methods=["POST"])
def save_file():
    data = request.get_json()
    project_name = data.get("project_name")
    file_path = data.get("file_path")
    content = data.get("content")
    
    if not all([project_name, file_path, content]):
        return jsonify({"error": "Missing fields"}), 400
        
    import builder
    success, msg = builder.apply_agent_edit(project_name, file_path, content)
    
    # Log to Mentor
    import mentor as mentor_module
    if success:
        mentor_module.mentor.log_event(f"User manually saved file: {file_path}")
    else:
        mentor_module.mentor.log_event(f"User failed to save {file_path}: {msg}")
    
    if success:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"error": msg}), 400


    else:
        return jsonify({"error": msg}), 400

@app.route("/api/terminal/run", methods=["POST"])
def terminal_run():
    # Define allowed commands and their arguments
    ALLOWED_COMMANDS = {
        'npm': ['install', 'test', 'run', 'build', 'start'],
        'python': ['-m', 'pip', 'install', '-m', 'http.server', '-m', 'pytest'],
        'pip': ['install', 'list', 'show'],
        'ls': ['-la', '-l', '-a'],
        'cat': [],
        'wc': ['-l', '-w', '-c'],
        'mkdir': [],
        'touch': [],
        'rm': ['-rf', '-r', '-f'],
        'cp': ['-r'],
        'mv': [],
        'git': ['status', 'add', 'commit', 'push', 'pull', 'clone', 'init']
    }

    def validate_command_parts(command_parts: List[str]) -> bool:
        """Validate command and arguments against whitelist"""
        if not command_parts:
            return False
        
        base_command = command_parts[0]
        
        # Check if command is allowed
        if base_command not in ALLOWED_COMMANDS:
            return False
        
        # Check arguments if any are provided
        if len(command_parts) > 1:
            allowed_args = ALLOWED_COMMANDS[base_command]
            for arg in command_parts[1:]:
                # Skip file/directory names (they don't start with -)
                if not arg.startswith('-'):
                    continue
                # Check if argument is allowed
                if arg not in allowed_args:
                    return False
        
        return True

    def secure_terminal_run(command: str, project_name: str) -> Dict[str, Any]:
        """
        Securely execute terminal commands with injection prevention
        """
        # Input validation
        if not command or not isinstance(command, str):
            return {"output": "Error: Invalid command", "error": "Invalid input"}
        
        if not project_name or not isinstance(project_name, str):
            return {"output": "Error: Invalid project name", "error": "Invalid input"}
        
        # Path validation
        try:
            project_root = get_secure_project_path(project_name)
        except ValueError as e:
            return {"output": f"Error: {str(e)}", "error": "Invalid project"}
        
        if not os.path.exists(project_root):
            return {"output": f"Error: Project path not found: {project_root}", "error": "Project not found"}
        
        # Parse command safely using shlex
        try:
            command_parts = shlex.split(command.strip())
        except ValueError as e:
            return {"output": f"Error: Invalid command syntax: {str(e)}", "error": "Parse error"}
        
        # Validate against whitelist
        if not validate_command_parts(command_parts):
            return {"output": "Error: Command not allowed", "error": "Unauthorized command"}
        
        # Additional safety: Check for dangerous patterns
        dangerous_patterns = ['&&', '||', ';', '|', '`', '$', '(', ')', '<', '>', '\n', '\r']
        for part in command_parts:
            for pattern in dangerous_patterns:
                if pattern in part:
                    return {"output": f"Error: Dangerous character detected: {pattern}", "error": "Security violation"}
        
        # Execute safely with shell=False
        try:
            result = subprocess.run(
                command_parts,
                shell=False,  # CRITICAL: Never use shell=True
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            output = result.stdout if result.stdout else result.stderr
            if not output:
                output = f"Command completed with exit code: {result.returncode}"
                
            return {"output": output, "exit_code": result.returncode}
            
        except subprocess.TimeoutExpired:
            return {"output": "Error: Command timed out after 30 seconds", "error": "Timeout"}
        except FileNotFoundError:
            return {"output": f"Error: Command not found: {command_parts[0]}", "error": "Command not found"}
        except Exception as e:
            return {"output": f"Execution Error: {str(e)}", "error": "Execution failed"}
    

@app.route("/api/voices", methods=["GET"])
def get_voices():
    # Proxy to ElevenLabs to get voices
    api_key = os.environ.get("ELEVENLABS_API_KEY") 
    # If not in env, check session or header? For now rely on Env or user-provided in header?
    # Better: Frontend sends key, or we hide it. Plan said "Input (if user provided) or use System Key"
    # Let's support an optional header 'X-ElevenLabs-Key'
    
    key = request.headers.get("X-ElevenLabs-Key") or api_key
    
    if not key:
        return jsonify({"voices": []}) # Return empty if no key
        
    try:
        url = "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": key}
        response = requests.get(url, headers=headers, timeout=10)
        if response.ok:
            return jsonify(response.json())
        return jsonify({"error": "Failed to fetch voices"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/settings/search", methods=["POST"])
def save_search_settings():
    data = request.get_json()
    key = data.get("key")
    if key:
        # Runtime override for this session/instance
        # Ideally save to .env or DB user profile
        os.environ["SERPER_API_KEY"] = key # Simple runtime override
        return jsonify({"status": "success"})
    return jsonify({"error": "No key"}), 400

@app.route("/api/tts", methods=["POST"])
def tts():
    data = request.get_json()
    text = data.get("text")
    voice_id = data.get("voice_id", "21m00Tcm4TlvDq8ikWAM") # Rachel default
    user_key = request.headers.get("X-ElevenLabs-Key")
    
    api_key = user_key or os.environ.get("ELEVENLABS_API_KEY")
    
    if not api_key:
        return jsonify({"error": "No ElevenLabs API Key"}), 401
    
    if not text:
        return jsonify({"error": "No text provided"}), 400
        
    try:
        # ElevenLabs Text-to-Speech
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }
        
        response = requests.post(url, json=payload, headers=headers, stream=True, timeout=30)
        
        if response.ok:
            return Response(response.iter_content(chunk_size=1024), content_type="audio/mpeg")
        else:
            return jsonify({"error": response.text}), response.status_code
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Mentor Routes ---
import mentor as mentor_module

@app.route("/api/mentor/log", methods=["POST"])
def mentor_log():
    data = request.get_json()
    event = data.get("event")
    if event:
        mentor_module.mentor.log_event(event)
    return jsonify({"status": "logged"})

@app.route("/api/mentor/tip", methods=["GET"])
def get_mentor_tip():
    project_name = request.args.get("project_name", "Unknown Project")
    tip = mentor_module.mentor.generate_tip(project_name)
    return jsonify({"tip": tip})

# --- Sandbox Routes ---
# Track running servers: {project_name: {"pid": int, "port": int, "proc": Popen}}
running_servers = {}

@app.route("/api/sandbox/start", methods=["POST"])
def sandbox_start():
    data = request.get_json()
    project_name = data.get("project_name")
    
    if not project_name:
        return jsonify({"error": "Project name required"}), 400
        
    # Check if already running
    if project_name in running_servers:
        info = running_servers[project_name]
        # Verify process still alive
        if info["proc"].poll() is None:
            return jsonify({"url": f"http://localhost:{info['port']}", "status": "running"})
        else:
            del running_servers[project_name]
            
    # Find free port (start at 8000, try up to 8100)
    import socket
    port = 8000
    for p in range(8000, 8100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', p)) != 0:
                port = p
                break
    
    project_root = os.path.join("projects", project_name)
    # Ideally serve from src or wherever index.html is. 
    # Let's check for 'src' folder
    serve_cwd = project_root
    if os.path.exists(os.path.join(project_root, "src")):
        serve_cwd = os.path.join(project_root, "src")
        
    if not os.path.exists(serve_cwd):
         return jsonify({"error": f"Path not found: {serve_cwd}"}), 404
         
    try:
        import subprocess
        # Start python http.server
        # We use a new process group or detached? Simple Popen for now.
        proc = subprocess.Popen(
            ["python", "-m", "http.server", str(port)],
            cwd=serve_cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False # Shell false is safer, mostly works on Windows for python command if in Path
        )
        
        running_servers[project_name] = {"pid": proc.pid, "port": port, "proc": proc}
        
        mentor_module.mentor.log_event(f"User started Live Sandbox on port {port}")
        
        return jsonify({"url": f"http://localhost:{port}", "status": "started"})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/test/run", methods=["POST"])
def run_tests():
    data = request.get_json()
    project_name = data.get("project_name")
    
    project_root = get_secure_project_path(project_name)
    src_dir = os.path.join(project_root, "src") # Tests usually here or root?
    
    # Detect Test Framework
    cmd = []
    if os.path.exists(os.path.join(project_root, "package.json")):
        cmd = ["npm", "test"]
    elif os.path.exists(os.path.join(src_dir, "requirements.txt")) or any(f.endswith(".py") for f in os.listdir(src_dir)):
        # Default to pytest
        cmd = ["pytest"] # Requires pytest installed
    else:
        return jsonify({"output": "No testing framework detected (package.json or pytest).", "exit_code": 1})
        
    try:
        import subprocess
        # Run tests
        # Capture stdout and stderr
        # CWD should be src_dir for python usually, or root for npm
        cwd = project_root if cmd[0] == "npm" else src_dir
        
        result = subprocess.run(
            cmd, 
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            text=True
        )
        
        return jsonify({
            "output": result.stdout,
            "exit_code": result.returncode
        })
    except Exception as e:
         return jsonify({"output": f"Execution Failed: {str(e)}", "exit_code": -1})

@app.route("/api/debug", methods=["POST"])
def auto_debug():
    data = request.get_json()
    project_name = data.get("project_name")
    error_log = data.get("error_log")
    
    if not all([project_name, error_log]):
         return jsonify({"error": "Missing info"}), 400
         
    try:
        # 1. Ask AI to Fix
        from builder import client, apply_agent_edit
        
        # Read files to give context? For now, we rely on error log containing file paths.
        # Or we give file listing.
        project_root = get_secure_project_path(project_name)
        src_dir = os.path.join(project_root, "src")
        
        system_prompt = f"""
        You are an expert Debugging Agent.
        Analyze the Test Output below and fix the code.
        Project: {project_name}
        
        Output MUST be a JSON object with:
        {{
            "thought": "Analysis of the error...",
            "action": "edit",
            "file": "filename.py",
            "content": "Full corrected content of the file"
        }}
        """
        
        response = client.chat.completions.create(
            model="kimi-k2-0905-preview",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"TEST OUTPUT:\n{error_log}"}
            ],
            response_format={"type": "json_object"}
        )
        
        import json
        reply = response.choices[0].message.content
        fix_data = json.loads(reply)
        
        file_path = fix_data.get("file")
        content = fix_data.get("content")
        thought = fix_data.get("thought")
        
        if file_path and content:
            success, msg = apply_agent_edit(project_name, file_path, content)
            return jsonify({
                "status": "fixed" if success else "failed", 
                "message": msg,
                "thought": thought
            })
        
        return jsonify({"status": "failed", "message": "AI could not generate a fix action."})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/sandbox/stop", methods=["POST"])
def sandbox_stop():
    data = request.get_json()
    project_name = data.get("project_name")
    
    if project_name in running_servers:
        info = running_servers[project_name]
        try:
            info["proc"].terminate()
            # info["proc"].wait() # Don't block
        except:
            pass
        del running_servers[project_name]
        mentor_module.mentor.log_event("User stopped Live Sandbox")
        return jsonify({"status": "stopped"})
        
    return jsonify({"status": "not_running"})

@app.route("/chat", methods=["POST"])
@limiter.limit("10 per minute")
def chat_with_agent():
    data = request.get_json()
    project_name = data.get("project_name")
    agent_role = data.get("agent_role")
    message = data.get("message") or "" # allow empty if image provided
    image_data = data.get("image_data")
    
    if not all([project_name, agent_role]) or (not message and not image_data):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # 1. Get Context
        history = memory.get_agent_context(project_name, agent_role)
        
        # 2. Call LLM
        # We use a chat completion here
        from builder import client # Reuse client
        
        system_prompt = f"You are the {agent_role} for the project '{project_name}'. Answer the user's questions based on your role."
        
        # 1.5 Get Project Context (File Structure)
        project_src = os.path.join("projects", project_name, "src") # Verify path logic matching builder.py
        file_list = []
        if os.path.exists(project_src):
            for root, dirs, files in os.walk(project_src):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), project_src)
                    file_list.append(rel_path)
        
        if file_list:
            system_prompt += f"\n\nCurrent Project Files:\n" + "\n".join([f"- {f}" for f in file_list])
            
        # Add Edit Instructions to System Prompt
        system_prompt += "\n" + prompt.AGENT_EDIT_PROMPT

        messages = [
            {"role": "system", "content": system_prompt},
        ]
        
        # Add history if we had a structured way, for now basic RAG-ish
        if history:
             messages.append({"role": "system", "content": f"Context/History:\n{history}"})
             
        user_content = []
        if message: user_content.append({"type": "text", "text": message})
        if image_data: user_content.append({"type": "image_url", "image_url": {"url": image_data}})
        
        messages.append({"role": "user", "content": user_content})

        # --- AUTO-HEALING LOOP ---
        max_retries = 1
        edit_result = None
        
        for attempt in range(max_retries + 1):
            response = client.chat.completions.create(
                model="kimi-k2-0905-preview",
                messages=messages,
                temperature=0.7
            )
            
            reply = response.choices[0].message.content
            
            # Check for Edit Action
            import re
            import builder
            
            # Simple heuristic
            if '"action": "edit"' in reply or "'action': 'edit'" in reply:
                # Find JSON blob
                json_match = re.search(r'\{.*"action":\s*"edit".*\}', reply, re.DOTALL)
                if json_match:
                    try:
                        action_data = json.loads(json_match.group(0))
                        if action_data.get("action") == "edit":
                            file_path = action_data.get("file")
                            content = action_data.get("content")
                            
                            success, msg = builder.apply_agent_edit(project_name, file_path, content)
                            edit_result = msg
                            
                            if success:
                                # Success! Append system feedback and break loop
                                reply += f"\n\n[SYSTEM]: {msg}"
                                break 
                            else:
                                # Failure!
                                if attempt < max_retries:
                                    # Feed error back to LLM and Retry
                                    error_feedback = f"Your edit to {file_path} failed validation with error: {msg}. Please fix the code and output the JSON again."
                                    messages.append({"role": "assistant", "content": reply})
                                    messages.append({"role": "system", "content": error_feedback})
                                    continue # Retry loop
                                else:
                                    # Final failure
                                    reply += f"\n\n[SYSTEM]: Edit Failed after retries: {msg}"
                                    break
                    except json.JSONDecodeError:
                        # JSON parsing failed, treat as no edit action or malformed
                        pass
                    except Exception as e:
                        # Other errors during edit application/parsing
                        print(f"Error during edit action processing: {e}")
                        pass
            
            # If no edit or basic reply, or edit was successful, break
            break
        
        # 3. Save Memory
        memory.save_memory(project_name, agent_role, f"User: {message}")
        memory.save_memory(project_name, agent_role, f"Agent: {reply}")
        
        return jsonify({"reply": reply, "edit_status": edit_result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/projects/<path:filename>")
def serve_project_file(filename):
    """
    Serve files from the projects source directory for preview.
    Note: In production, this needs stricter security (chroot/sandbox).
    """
    from flask import send_from_directory
    
    # We assume filename is like "ProjectName/src/index.html"
    # But our safe_name logic replaces spaces with underscores.
    # Frontend needs to know the exact path.
    
    # Let's map "projects/" to the local "projects" folder
    # filename will be "MyProject/src/index.html"
    
    PROJECTS_ROOT = os.path.join(os.getcwd(), "projects")
    return send_from_directory(PROJECTS_ROOT, filename)

# ------------------------------------------------------------------
# Admin Dashboard
# ------------------------------------------------------------------
def check_admin_auth():
    auth = request.authorization
    if not auth or not (auth.username == 'admin' and auth.password == os.getenv('ADMIN_PASSWORD', 'admin123')):
        return False
    return True

@app.route("/admin")
def admin_dashboard():
    if not check_admin_auth():
        return Response(
            'Could not verify your access level for that URL.\n'
            'You have to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'})
    
    # Analytics
    total_users = User.query.count()
    active_subs = User.query.filter_by(is_subscribed=True).count()
    projects_count = Project.query.count()
    recent_users = User.query.order_by(User.trial_start_date.desc()).limit(10).all()
    
    return render_template(
        "admin.html", 
        total_users=total_users, 
        active_subs=active_subs, 
        projects_count=projects_count,
        recent_users=recent_users
    )


# ------------------------------------------------------------------
# Billing & Subscription Routes
# ------------------------------------------------------------------
@app.route("/api/packages", methods=["GET"])
def get_packages():
    # Seed if empty
    if Package.query.count() == 0:
        db.session.add(Package(id=1, name="Starter", price=0.0, limit_builds=1, limit_voice_chars=0))
        db.session.add(Package(id=2, name="Pro", price=29.0, limit_builds=50, limit_voice_chars=50000))
        db.session.add(Package(id=3, name="Enterprise", price=199.0, limit_builds=9999, limit_voice_chars=999999))
        db.session.commit()
    
    pkgs = Package.query.all()
    return jsonify([{"id": p.id, "name": p.name, "price": p.price} for p in pkgs])

@app.route("/api/billing/subscribe", methods=["POST"])
def subscribe_package():
    data = request.get_json()
    pkg_id = data.get("package_id")
    
    # Mock Auth: Use 'test_user' for now
    user_id = "test_user" 
    user = User.query.get(user_id)
    if not user:
        user = User(username=user_id)
        db.session.add(user)
    
    pkg = Package.query.get(pkg_id)
    if not pkg: return jsonify({"status": "error", "message": "Invalid Package"}), 400
    
    # Update User
    user.package_id = pkg.id
    user.credits_left = pkg.limit_builds
    user.voice_chars_left = pkg.limit_voice_chars
    user.subscription_status = "active"
    
    # Create Transaction
    txn = Transaction(user_id=user.username, package_id=pkg.id, amount=pkg.price)
    db.session.add(txn)
    db.session.commit()
    
    return jsonify({"status": "success"})

@app.route("/billing")
def billing_page():
    user = User.query.get("test_user") 
    if not user: 
        user = User(username="test_user", package_id=1)
        db.session.add(user)
        db.session.commit()
        
    txns = Transaction.query.filter_by(user_id=user.username).order_by(Transaction.timestamp.desc()).all()
    for t in txns:
        p = Package.query.get(t.package_id)
        t.package_name = p.name if p else "Unknown"
        
    return render_template("billing.html", user=user, transactions=txns)

@app.route("/pricing")
def pricing_page():
    return render_template("pricing.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

class CommandSanitizer:
    """Advanced command input sanitization"""
    
    # Dangerous shell metacharacters and patterns
    DANGEROUS_CHARS = r'[;&|`$()<>\\n\\r]'
    DANGEROUS_PATTERNS = [
        r'&&', r'\|\|', r';', r'\|', r'`', r'\$\(',
        r'\${', r'<', r'>', r'\n', r'\r', r'\\x',
        r'eval\s*\(', r'exec\s*\(', r'system\s*\('
    ]
    
    @staticmethod
    def sanitize_input(user_input: str) -> Optional[str]:
        """Comprehensive input sanitization"""
        if not user_input or not isinstance(user_input, str):
            return None
            
        # Remove null bytes
        user_input = user_input.replace('\x00', '')
        
        # Check for dangerous characters
        if re.search(CommandSanitizer.DANGEROUS_CHARS, user_input):
            return None
            
        # Check for dangerous patterns
        for pattern in CommandSanitizer.DANGEROUS_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                return None
                
        # Additional checks for encoded payloads
        if '%' in user_input:
            try:
                # Check for URL-encoded dangerous characters
                import urllib.parse
                decoded = urllib.parse.unquote(user_input)
                if re.search(CommandSanitizer.DANGEROUS_CHARS, decoded):
                    return None
            except:
                return None
                
        return user_input.strip()

    @staticmethod
    def validate_filename(filename: str) -> Optional[str]:
        """Secure filename validation"""
        if not filename:
            return None
            
        # Remove path components
        from pathlib import Path
        safe_name = Path(filename).name
        
        # Check for empty filename after path removal
        if not safe_name or safe_name.startswith('.'):
            return None
            
        # Validate extension
        allowed_extensions = {'.txt', '.md', '.py', '.js', '.json', '.yml', '.yaml'}
        ext = Path(safe_name).suffix.lower()
        if ext not in allowed_extensions:
            return None
            
        return safe_name

class CommandCategory(Enum):
    """Command categories for granular control"""
    FILE_SYSTEM = "filesystem"
    VERSION_CONTROL = "vcs"
    PACKAGE_MANAGER = "package"
    TESTING = "testing"
    BUILD = "build"

@dataclass
class WhitelistedCommand:
    """Represents a whitelisted command"""
    command: str
    category: CommandCategory
    allowed_args: Set[str]
    max_args: int = 10
    requires_file: bool = False

# Comprehensive whitelist
WHITELISTED_COMMANDS = [
    WhitelistedCommand("ls", CommandCategory.FILE_SYSTEM, {"-la", "-l", "-a", "-h"}),
    WhitelistedCommand("cat", CommandCategory.FILE_SYSTEM, set(), requires_file=True),
    WhitelistedCommand("wc", CommandCategory.FILE_SYSTEM, {"-l", "-w", "-c"}, requires_file=True),
    WhitelistedCommand("npm", CommandCategory.PACKAGE_MANAGER, {"install", "test", "run", "build"}),
    WhitelistedCommand("python", CommandCategory.BUILD, {"-m", "pip"}, max_args=5),
    WhitelistedCommand("git", CommandCategory.VERSION_CONTROL, {"status", "add", "commit", "push", "pull"}),
    WhitelistedCommand("pytest", CommandCategory.TESTING, {"-v", "-x", "--tb=short"}),
]

class CommandWhitelist:
    """Manages whitelisted commands"""
    
    def __init__(self):
        self.commands = {cmd.command: cmd for cmd in WHITELISTED_COMMANDS}
    
    def validate_command(self, command_parts: List[str]) -> bool:
        """Validate command against whitelist"""
        if not command_parts:
            return False
            
        base_cmd = command_parts[0]
        cmd_config = self.commands.get(base_cmd)
        
        if not cmd_config:
            return False
            
        # Check argument count
        if len(command_parts) - 1 > cmd_config.max_args:
            return False
            
        # Validate arguments
        for arg in command_parts[1:]:
            if arg.startswith('-') and arg not in cmd_config.allowed_args:
                return False
                
        return True