"""
Enterprise AI-Agent Generator
-----------------------------
Takes a one-line idea from the user and spins up 30 specialised AI-agent roles
that map to every real-world department/team you would find in an industrial-grade
software company (marketing → research → exec and everything in-between).

Usage
-----
$ export MOONSHOT_API_KEY="sk-……"
$ python agent_builder.py
Idea: serverless observability platform
→ agents.json   (30 AI roles)
"""

import json
import os
import sys
from openai import OpenAI
import prompt

# ------------------------------------------------------------------
# 1. OpenAI-compatible Moon-shot client
# ------------------------------------------------------------------
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url="https://api.moonshot.ai/v1"
)

def generate_agents(idea):
    """
    Generates a list of agents based on the provided idea using the Moonshot API.
    """
    # ------------------------------------------------------------------
    # 2. Fire the request (non-streaming so we can parse JSON)
    # ------------------------------------------------------------------
    try:
        response = client.chat.completions.create(
            model="kimi-k2-0905-preview",
            messages=[
                {"role": "system", "content": prompt.SYSTEM_PROMPT},
                {"role": "user", "content": idea}
            ],
            temperature=0.3,
            max_tokens=8192,
            top_p=1,
            stream=False
        )
        content = response.choices[0].message.content
        
        # ------------------------------------------------------------------
        # 3. Parse & validate JSON
        # ------------------------------------------------------------------
        agents_data = json.loads(content)
        

        # Depending on how the model returns it, it might be the full object or just the agents list
        # The prompt asks for a JSON object with "project" and "agents" keys.
        if "agents" in agents_data:
             if len(agents_data["agents"]) > 30:
                 pass
        
        # ------------------------------------------------------------------
        # 4. Save to Project Folder
        # ------------------------------------------------------------------
        project_name = "Untitled_Project"
        if "project" in agents_data and "name" in agents_data["project"]:
             project_name = agents_data["project"]["name"].replace(" ", "_").replace("/", "-")
        else:
             # Fallback: sanitize idea
             project_name = idea.split()[0:3] 
             project_name = "_".join(project_name).replace(" ", "_").replace("/", "-")

        project_dir = os.path.join("projects", project_name)
        os.makedirs(project_dir, exist_ok=True)

        output_file = os.path.join(project_dir, "agents.json")
        with open(output_file, "w", encoding="utf-8") as fh:
            json.dump(agents_data, fh, indent=2, ensure_ascii=False)
            
        # Add local path to result so app can use it
        agents_data["local_path"] = output_file
        agents_data["project_name"] = project_name
        
        return agents_data

    except Exception as exc:
        print(f"Error during generation: {exc}")
        raise exc

# ------------------------------------------------------------------
# 4. CLI Entry point
# ------------------------------------------------------------------
if __name__ == "__main__":
    # Grab idea from CLI
    if len(sys.argv) > 1:
        idea = " ".join(sys.argv[1:])
    else:
        idea = input("Idea: ").strip()

    if not idea:
        sys.exit("No idea provided.")

    try:
        data = generate_agents(idea)
        print(f"✅  Result saved to {data.get('local_path', 'unknown')}")

    except Exception as e:
        sys.exit(f"Failed: {e}")

