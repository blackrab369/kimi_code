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

# ------------------------------------------------------------------
# 2. System prompt that forces *only* valid JSON array
# ------------------------------------------------------------------


BASIC_SYSTEM_PROMPT = """
You are an enterprise AI architect.
The user will supply a short product/feature idea.

Reply with **ONLY** a JSON array (no markdown, no commentary) of 30 objects.
Each object must have:
{
  "role": "string",           # human-readable job title
  "department": "string",     # department/team name
  "goal": "string",           # 1-sentence mission for this agent
  "key_tasks": ["string"]     # 2-4 core responsibilities
}

Cover every area of a real software company:
Marketing, Sales, Product, UX, Engineering, QA, DevOps, SRE, Security,
IT, Data-Engineering, Analytics, Research, Customer-Success, Support,
Legal, Compliance, Finance, HR, Talent, People-Ops, Partnerships,
Solutions-Engineering, Solutions-Architecture, Professional-Services,
Training, Documentation, Community, Growth, Strategy, Executive.
"""


# ------------------------------------------------------------------
# 3. Grab idea from CLI (or fall back to stdin)
# ------------------------------------------------------------------
if len(sys.argv) > 1:
    idea = " ".join(sys.argv[1:])
else:
    idea = input("Idea: ").strip()

if not idea:
    sys.exit("No idea provided.")

# ------------------------------------------------------------------
# 4. Fire the request (non-streaming so we can parse JSON)
# ------------------------------------------------------------------
try:
    response = client.chat.completions.create(
        model="kimi-k2-0905-preview",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": idea}
        ],
        temperature=0.3,
        max_tokens=8192,
        top_p=1,
        stream=False
    )
    content = response.choices[0].message.content
except Exception as exc:
    sys.exit(f"Moonshot API failed: {exc}")

# ------------------------------------------------------------------
# 5. Parse & validate JSON
# ------------------------------------------------------------------
try:
    agents = json.loads(content)
    if not isinstance(agents, list) or len(agents) > 30:
        raise ValueError("Malformed array")
except Exception:
    # Dump raw reply for debugging
    sys.exit(f"Model returned invalid JSON.\nRaw reply:\n{content}")

# ------------------------------------------------------------------
# 6. Save tidy result
# ------------------------------------------------------------------
output_file = "agents.json"
with open(output_file, "w", encoding="utf-8") as fh:
    json.dump({"idea": idea, "agents": agents}, fh, indent=2, ensure_ascii=False)

print(f"✅  {len(agents)} AI agent roles written to {output_file}")