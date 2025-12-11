# Kimi AI Software Builder 🚀

**The Ultimate AI-Powered Development Workspace**

Kimi AI Software Builder is a next-generation local development platform that pairs you with a team of AI Agents (Product Manager, Architect, Engineer, QA) to build, refine, and deploy web applications entirely through natural language.

---

## ✨ Key Features

### 🧠 AI Development Team
-   **Multi-Agent Architecture**: Collaborative agents handle different aspects of the SDLC (Planning, Coding, Testing).
-   **Auto-Healing**: The system automatically detects build errors and triggers agents to fix them.
-   **Context-Aware**: Agents are aware of your existing file structure and project history.

### 🛠️ Interactive Workspace
-   **Web-Based Editor**: Full Monaco Editor integration for manual code adjustments.
-   **Interactive Terminal**: Run shell commands directly from the browser (`npm install`, `python server.py`, etc.).
-   **Live Sandbox**: Instantly host your static web projects locally and view them in a side-by-side **Split View**.
-   **"My Projects" Dashboard**: Manage multiple projects with ease.

### 🎙️ Voice & Mentor
-   **Voice Interface**: Speak to your agents using the microphone.
-   **ElevenLabs Integration**: High-quality AI narration for status updates.
-   **Mentor Agent**: A background observer that monitors your progress and offers proactive verbal tips (*"I noticed you fixed that bug, nice work!"*).

### ⚙️ Power Tools
-   **Deployment Center**:
    -   **Vercel**: Auto-generate `vercel.json` for instant frontend deployment.
    -   **Supabase**: Inject configuration for backend database & auth.
-   **Agent Persona Editor**: Customize your team! Change "QA Bot" to "Steve Jobs" for stricter feedback.
-   **Export to ZIP**: Download your full source code with one click.
-   **Time Travel**: Automatic file backups allow you to revert changes if an agent messes up.

### 🎨 Personalization
-   **Themes**: Choose your vibe – Midnight (Default), Cyberpunk (Neon), Matrix (Hacker), or Professional (Light).

---

## 🚀 Getting Started

### Prerequisites
-   Python 3.8+
-   OpenAI API Key (or Moonshot/Compatible API)
-   ElevenLabs API Key (Optional, for premium voice)

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/your-repo/kimi-code.git
    cd kimi-code
    ```
2.  Install dependencies:
    ```bash
    pip install flask flask-sqlalchemy flask-limiter requests openai
    ```
    *(Note: requirements.txt generation is recommended)*

3.  Configure Environment:
    -   Set your API keys in the interface Settings modal, or via environment variables.

4.  Run the Server:
    ```bash
    python app.py
    ```
5.  Open your browser to:
    `http://localhost:5000`

---

## 📖 Usage Guide

### 1. Create a Project
Type your idea into the chat box (e.g., *"Build a snake game in Python"*). The agents will generate a plan, write the code, and verify it.

### 2. Live Preview
Click the **▶ Run Live** button to spin up a local server and see your web app running instantly in the right-hand panel.

### 3. Edit & Refine
-   **Manual**: Click any file in the file tree to open the Code Editor.
-   **Agentic**: Ask the chat to *"Change the background to blue"* or *"Fix the collision bug"*.

### 4. Deploy
Click **🚀 Deploy** to open the Deployment Center.
-   Generate a Vercel config for your frontend.
-   Connect a Supabase backend for data.

### 5. Export
Click **⬇ Source** to download a ZIP file of your project.

---

## 🔒 Security & Monetization
-   **Rate Limiting**: Built-in limits for Free/Pro tiers.
-   **PayPal Integration**: Subscription management for Pro features.
-   **Sandboxing**: (Note: Local execution of generated code happens on your machine. Review code before running).

---

## 🤝 Contributing
Contributions are welcome! Please open an issue or pull request.

## 📄 License
MIT License.
