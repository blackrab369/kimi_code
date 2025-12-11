document.addEventListener('DOMContentLoaded', () => {
    const generateBtn = document.getElementById('generateBtn');
    const ideaInput = document.getElementById('ideaInput');
    const resultSection = document.getElementById('resultSection');
    const projectInfo = document.getElementById('projectInfo');
    const agentsGrid = document.getElementById('agentsGrid');
    const agentCount = document.getElementById('agentCount');

    // Settings Elements
    const settingsBtn = document.getElementById('settingsBtn');
    const settingsModal = document.getElementById('settingsModal');
    const closeBtn = document.querySelector('.close');
    const saveTokenBtn = document.getElementById('saveTokenBtn');
    const githubTokenInput = document.getElementById('githubToken');
    const tokenStatus = document.getElementById('tokenStatus');
    const githubStatus = document.getElementById('githubStatus');

    // Settings Modal
    if (settingsBtn) {
        settingsBtn.addEventListener('click', () => settingsModal.classList.remove('hidden'));
        closeBtn.addEventListener('click', () => settingsModal.classList.add('hidden'));
        window.addEventListener('click', (e) => {
            if (e.target == settingsModal) settingsModal.classList.add('hidden');
        });

        saveTokenBtn.addEventListener('click', async () => {
            const token = githubTokenInput.value.trim();
            if (!token) return;

            saveTokenBtn.disabled = true;
            saveTokenBtn.textContent = 'Verifying...';

            try {
                const res = await fetch('/settings/github', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token })
                });
                const data = await res.json();

                if (data.status === 'success') {
                    tokenStatus.textContent = `✅ Connected as ${data.username}`;
                    tokenStatus.style.color = '#10b981';
                    setTimeout(() => settingsModal.classList.add('hidden'), 1500);
                } else {
                    tokenStatus.textContent = `❌ ${data.message}`;
                    tokenStatus.style.color = '#ef4444';
                }
            } catch (e) {
                tokenStatus.textContent = '❌ Error saving token';
            } finally {
                saveTokenBtn.disabled = false;
                saveTokenBtn.textContent = 'Save Token';
            }
        });

        const saveSearchKeyBtn = document.getElementById('saveSearchKeyBtn');
        const serperKeyInput = document.getElementById('serperKey');

        saveSearchKeyBtn.addEventListener('click', async () => {
            const key = serperKeyInput.value.trim();
            if (!key) return;

            saveSearchKeyBtn.disabled = true;
            saveSearchKeyBtn.innerText = "Saving...";

            try {
                await fetch('/settings/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ key })
                });
                alert("Search Key Saved!");
            } catch (e) {
                alert("Error saving key");
            } finally {
                saveSearchKeyBtn.disabled = false;
                saveSearchKeyBtn.innerText = "Save Search Key";
            }
        });
    }

    generateBtn.addEventListener('click', generateTeam);
    ideaInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') generateTeam();
    });

    async function generateTeam() {
        const idea = ideaInput.value.trim();
        if (!idea) return;

        // UI Loading State
        generateBtn.disabled = true;
        generateBtn.classList.add('loading');
        resultSection.classList.add('hidden');
        agentsGrid.innerHTML = '';
        projectInfo.innerHTML = '';
        if (githubStatus) githubStatus.classList.add('hidden'); // Reset

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ idea })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.error || 'Failed to generate');
            }

            const data = await response.json();
            renderResults(data);

        } catch (error) {
            alert('Error: ' + error.message);
        } finally {
            generateBtn.disabled = false;
            generateBtn.classList.remove('loading');
        }
    }

    function renderResults(data) {
        resultSection.classList.remove('hidden');

        // GitHub Status
        if (githubStatus) {
            if (data.github_status === 'success') {
                githubStatus.classList.remove('hidden');
                githubStatus.innerHTML = `<span>☁️ Synced to <a href="${data.github_repo_url}" target="_blank" style="color:inherit">GitHub</a></span>`;
            } else if (data.github_status === 'failed') {
                githubStatus.classList.remove('hidden');
                githubStatus.innerHTML = `<span>⚠️ GitHub Sync Failed</span>`;
                githubStatus.style.color = '#ef4444';
                githubStatus.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                githubStatus.style.background = 'rgba(239, 68, 68, 0.1)';
            }
        }

        // Render Project Info
        // Check if project info exists in the response
        if (data.project) {
            const techs = data.project.tech_stack
                ? data.project.tech_stack.map(t => `<span class="tag">${t}</span>`).join('')
                : '';

            projectInfo.innerHTML = `
                <h3 class="project-title">${data.project.name || 'Unnamed Project'}</h3>
                <p class="pro-desc">${data.project.description || ''}</p>
                <div class="tech-tags">${techs}</div>
            `;
        } else {
            // Fallback if structured differently or just list of agents
            projectInfo.innerHTML = `<h3 class="project-title">${data.idea || 'Generated Team'}</h3>`;
        }

        // Render Agents
        const agents = data.agents || [];
        agentCount.textContent = `(${agents.length})`;

        // Show Build Button
        const buildBtn = document.getElementById('buildBtn');
        const buildOutput = document.getElementById('buildOutput');
        const terminalContent = document.getElementById('terminalContent');
        const fileTree = document.getElementById('fileTree');

        const previewBtn = document.createElement('button');
        previewBtn.textContent = "👁️ Live Preview";
        previewBtn.className = "secondary-btn hidden";
        previewBtn.style.marginLeft = "10px";

        if (buildBtn) {
            if (!document.getElementById('previewBtn')) {
                previewBtn.id = 'previewBtn'; // Assign ID to prevent duplicates if re-run
                buildBtn.parentNode.appendChild(previewBtn);
            }
            buildBtn.classList.remove('hidden');

            // Device Preview Logic
            previewBtn.onclick = async () => {
                previewBtn.disabled = true;
                previewBtn.textContent = "⏳ Starting...";

                // 1. Start Sandbox
                const safeProjectName = data.project_name || data.project.name.replace(/ /g, '_').replace(/\//g, '-');
                try {
                    const res = await fetch('/api/sandbox/start', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ project_name: safeProjectName })
                    });
                    const sandboxData = await res.json();

                    if (sandboxData.url) {
                        // 2. Open Modal
                        const modal = document.getElementById('previewModal');
                        const iframe = document.getElementById('previewFrame');
                        modal.classList.remove('hidden');
                        iframe.src = sandboxData.url;
                        previewBtn.textContent = "👁️ Live Preview";
                    } else {
                        alert("Failed to start sandbox: " + sandboxData.error);
                    }
                } catch (e) {
                    alert("Sandbox Error: " + e.message);
                } finally {
                    previewBtn.disabled = false;
                    previewBtn.textContent = "👁️ Live Preview";
                }
            };

            // Global Resize Helper
            window.resizePreview = (width) => {
                document.getElementById('previewFrame').style.width = width;
            };

            // Store data for build
            buildBtn.onclick = async () => {
                buildBtn.disabled = true;
                buildBtn.classList.add('loading');
                buildOutput.classList.remove('hidden');
                terminalContent.textContent = '> Initializing Engineering Agent...\n> Analyzing project requirements...\n';

                if (window.speakCheck) window.speakCheck("Starting build process. Initializing agents.", true);

                try {
                    const res = await fetch('/build', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ agents_data: data })
                    });

                    if (!res.ok) throw new Error('Build failed');

                    // STREAMING READER
                    const reader = res.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';

                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;

                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\n');
                        buffer = lines.pop(); // Keep partial line

                        for (const line of lines) {
                            if (!line.trim()) continue;
                            try {
                                const msg = JSON.parse(line);

                                // HANDLERS
                                if (msg.status === 'thinking') {
                                    terminalContent.textContent += `> [${msg.agent}]: ${msg.message}\n`;
                                    terminalContent.scrollTop = terminalContent.scrollHeight;
                                }
                                else if (msg.status === 'thought') {
                                    terminalContent.textContent += `> [${msg.agent}]: (Thinking) ${msg.message.substring(0, 50)}...\n`;
                                }
                                else if (msg.status === 'search') {
                                    // SEARCH UI HANDLING
                                    const panel = document.getElementById('searchPanel');
                                    if (panel) panel.classList.remove('hidden');

                                    const resultsDiv = document.getElementById('searchResults');
                                    if (resultsDiv) {
                                        const item = document.createElement('div');
                                        item.className = 'search-item';
                                        item.innerHTML = `
                                            <div class="search-query" style="font-weight:bold; color:#aeda15; margin-bottom:4px;">🔍 ${msg.query}</div>
                                            <div class="search-status" style="font-size:0.8em; color:#888;">Scanning web resources...</div>
                                        `;
                                        resultsDiv.appendChild(item);
                                        resultsDiv.scrollTop = resultsDiv.scrollHeight;
                                    }
                                    terminalContent.textContent += `> [Search]: ${msg.query}\n`;
                                }
                                else if (msg.status === 'file') {
                                    terminalContent.textContent += `> [FS]: Wrote ${msg.file}\n`;
                                    const tag = document.createElement('span');
                                    tag.className = 'file-tag';
                                    tag.innerText = `📄 ${msg.file}`;
                                    fileTree.appendChild(tag);
                                }
                                else if (msg.status === 'complete') {
                                    terminalContent.textContent += `\n> Build Complete! Output: ${msg.directory}\n`;
                                    if (window.speakCheck) window.speakCheck("Build complete.", true);
                                }
                                else if (msg.status === 'error' || msg.status === 'fatal') {
                                    terminalContent.textContent += `> ERROR: ${msg.message}\n`;
                                }

                                terminalContent.scrollTop = terminalContent.scrollHeight;

                            } catch (e) {
                                console.error("JSON Parse Error", e);
                            }
                        }
                    }

                } catch (e) {
                    terminalContent.textContent += `> Critical Build Failure: ${e.message}`;
                } finally {
                    buildBtn.disabled = false;
                    buildBtn.classList.remove('loading');
                }
            };
        }

        agents.forEach(agent => {
            const tasksHtml = agent.key_tasks
                ? `<ul class="tasks-list">${agent.key_tasks.map(t => `<li>${t}</li>`).join('')}</ul>`
                : '';

            const card = document.createElement('div');
            card.className = 'agent-card';
            card.innerHTML = `
                <div class="agent-role">${agent.role}</div>
                <div class="agent-dept">${agent.department}</div>
                <div class="agent-goal">${agent.goal}</div>
                ${tasksHtml}
            `;
            agentsGrid.appendChild(card);
        });

        // Scroll to results
        resultSection.scrollIntoView({ behavior: 'smooth' });

        // Initialize Chat
        initChat(data);

        // Initialize Editor
        initEditor(data);

        // Initialize Terminal
        initTerminal(data);
    }

    let term = null;

    function initTerminal(data) {
        const container = document.getElementById('xterm-container');
        const input = document.getElementById('terminalInput');

        if (!term) {
            term = new Terminal({
                theme: { background: '#1e1e1e' },
                cursorBlink: true,
                convertEol: true
            });
            const fitAddon = new FitAddon.FitAddon();
            term.loadAddon(fitAddon);
            term.open(container);
            fitAddon.fit();

            term.write('Welcome to Antigravity Terminal v1.0\r\n');
            term.write(`Project: ${data.project_name || 'Untitled'}\r\n$ `);
        }

        input.addEventListener('keypress', async (e) => {
            if (e.key === 'Enter') {
                const cmd = input.value.trim();
                input.value = '';

                if (!cmd) return;

                term.write(cmd + '\r\n'); // Echo command

                const safeProjectName = data.project_name || data.project.name.replace(/ /g, '_').replace(/\//g, '-');

                try {
                    const res = await fetch('/api/terminal/run', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            command: cmd,
                            project_name: safeProjectName
                        })
                    });
                    const result = await res.json();
                    term.write(result.output.replace(/\n/g, '\r\n') + '\r\n$ ');
                } catch (err) {
                    term.write(`Error: ${err.message}\r\n$ `);
                }
            }
        });

        // Also capture Build Output here if possible? 
        // For now, Build button still uses its own logic. 
        // We could pipe build output to Xterm too.
    }

    let editorInstance = null;

    function initEditor(data) {
        const editorModal = document.getElementById('editorModal');
        const closeEditor = document.querySelector('.close-editor');
        const saveFileBtn = document.getElementById('saveFileBtn');
        const editorFileName = document.getElementById('editorFileName');

        // Close handlers
        closeEditor.onclick = () => editorModal.classList.add('hidden');

        // Wait for Monaco to load
        require(['vs/editor/editor.main'], function () {
            // Monaco is ready
        });

        // 1. Hook up File Tree Clicks
        const fileTags = document.querySelectorAll('.file-tag');
        fileTags.forEach(tag => {
            const fileName = tag.textContent.replace('📄 ', '').replace('🗑 ', ''); // simple parsing

            tag.style.cursor = 'pointer';
            tag.onclick = async () => {
                editorModal.classList.remove('hidden');
                editorFileName.textContent = fileName;

                // Fetch File Content
                // Note: We need a way to get content. 
                // Currently we don't have a direct /api/file route, but we have static serving /projects/...
                // Construct path: projects/<ProjectName>/src/<file>
                // Need to handle safe name logic again?
                // Best to ask backend for file content via API to be safe.
                // Let's assume we can fetch from static structure for MVP read.
                // Or better, add a simple route later.
                // For now, let's try fetch from static.

                // data.project.name might have spaces, backend replaced them.
                // Let's rely on data.project_name if available (from generate response)
                const safeProjectName = data.project_name || data.project.name.replace(/ /g, '_').replace(/\//g, '-');
                const filePath = `/projects/${safeProjectName}/src/${fileName}`;

                try {
                    const res = await fetch(filePath);
                    if (!res.ok) throw new Error("File not found");
                    const content = await res.text();

                    // Determine Language
                    let lang = 'plaintext';
                    if (fileName.endsWith('.py')) lang = 'python';
                    if (fileName.endsWith('.js')) lang = 'javascript';
                    if (fileName.endsWith('.html')) lang = 'html';
                    if (fileName.endsWith('.css')) lang = 'css';
                    if (fileName.endsWith('.json')) lang = 'json';
                    if (fileName.endsWith('.cs')) lang = 'csharp';

                    // Create or Update Editor
                    if (editorInstance) {
                        editorInstance.setValue(content);
                        monaco.editor.setModelLanguage(editorInstance.getModel(), lang);
                    } else {
                        editorInstance = monaco.editor.create(document.getElementById('monaco-container'), {
                            value: content,
                            language: lang,
                            theme: 'vs-dark',
                            automaticLayout: true
                        });
                    }

                } catch (e) {
                    alert("Error loading file: " + e.message);
                }
            };
        });

        // 2. Save Logic
        saveFileBtn.onclick = async () => {
            const content = editorInstance.getValue();
            const fileName = editorFileName.textContent;
            const safeProjectName = data.project_name || data.project.name.replace(/ /g, '_').replace(/\//g, '-');

            saveFileBtn.textContent = "Saving...";
            saveFileBtn.disabled = true;

            try {
                const res = await fetch('/api/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_name: safeProjectName,
                        file_path: fileName,
                        content: content
                    })
                });

                const result = await res.json();
                if (res.ok) {
                    alert("Saved! " + result.message);
                    editorModal.classList.add('hidden');
                } else {
                    alert("Error saving: " + result.error);
                }
            } catch (e) {
                alert("Network Error: " + e.message);
            } finally {
                saveFileBtn.textContent = "💾 Save Changes";
                saveFileBtn.disabled = false;
            }
        };
    }

    function initChat(data) {
        const chatSection = document.getElementById('chatSection');
        const chatAgentList = document.getElementById('chatAgentList');
        const chatHeader = document.getElementById('chatHeader');
        const chatMessages = document.getElementById('chatMessages');
        const chatInput = document.getElementById('chatInput');
        const sendBtn = document.getElementById('sendMessageBtn');
        const closeChatBtn = document.getElementById('closeChatBtn');

        // Voice Elements
        let recognition = null;
        let isListening = false;
        const voiceBtn = document.createElement('button');
        voiceBtn.innerHTML = '🎤';
        voiceBtn.className = 'icon-btn';
        voiceBtn.style.marginRight = '10px';
        chatInput.parentNode.insertBefore(voiceBtn, chatInput);

        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;

            recognition.onresult = (event) => {
                const text = event.results[0][0].transcript;
                chatInput.value = text;
                sendMessage(); // Auto-send? Or let user confirm? Let's auto-send for "Conversation" feel
            };

            recognition.onend = () => {
                isListening = false;
                voiceBtn.style.color = 'inherit';
                voiceBtn.classList.remove('pulsing');
            };
        } else {
            voiceBtn.style.display = 'none';
        }

        voiceBtn.onclick = () => {
            if (!recognition) return;
            if (isListening) {
                recognition.stop();
            } else {
                recognition.start();
                isListening = true;
                voiceBtn.style.color = '#ef4444';
                voiceBtn.classList.add('pulsing'); // Assume CSS has pulsing anim
            }
        };

        let currentAgent = null;
        let projectName = data.project ? data.project.name : "Untitled";

        // Show Chat Section (could be hidden initially until user clicks a "Chat" button, 
        // but for now let's just expose it or add a toggle)
        chatSection.classList.remove('hidden');

        // Populate Agent List
        chatAgentList.innerHTML = '';
        data.agents.forEach(agent => {
            const li = document.createElement('li');
            li.textContent = agent.role;
            li.onclick = () => selectAgent(agent);
            chatAgentList.appendChild(li);
        });

        function selectAgent(agent) {
            currentAgent = agent;
            chatHeader.textContent = `Chatting with ${agent.role}`;
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatMessages.innerHTML = ''; // Clear for now, ideally load history

            // Highlight active
            Array.from(chatAgentList.children).forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
        }

        async function sendMessage() {
            const msg = chatInput.value.trim();
            if (!msg || !currentAgent) return;

            // Add User Message
            addMessage(msg, 'user');
            chatInput.value = '';
            chatInput.disabled = true;

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_name: projectName,
                        agent_role: currentAgent.role,
                        message: msg
                    })
                });

                const data = await res.json();
                if (data.reply) {
                    addMessage(data.reply, 'agent');
                    if (window.speakCheck) window.speakCheck(data.reply); // Audio Guidance
                } else {
                    addMessage('Error: ' + (data.error || 'Unknown'), 'agent');
                }

            } catch (e) {
                addMessage('Network Error', 'agent');
            } finally {
                chatInput.disabled = false;
                chatInput.focus();
            }
        }

        function addMessage(text, type, imgSrc = null) {
            const div = document.createElement('div');
            div.className = `message ${type}`;
            if (imgSrc) {
                div.innerHTML = `<img src="${imgSrc}" style="max-width:200px; border-radius:5px; display:block; margin-bottom:5px;">` + text;
            } else {
                div.textContent = text;
            }
            chatMessages.appendChild(div);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        // Removed local speak function in favor of window.speakCheck
        sendBtn.onclick = sendMessage;
        chatInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

        // --- Vision Integration ---
        const attachBtn = document.createElement('button');
        attachBtn.innerHTML = '📷';
        attachBtn.className = 'icon-btn';
        attachBtn.style.marginRight = '5px';
        chatInput.parentNode.insertBefore(attachBtn, chatInput);

        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = 'image/*';
        fileInput.style.display = 'none';
        chatInput.parentNode.appendChild(fileInput);

        let currentImage = null;
        attachBtn.onclick = () => fileInput.click();
        fileInput.onchange = (e) => {
            if (e.target.files[0]) {
                const reader = new FileReader();
                reader.onload = (evt) => {
                    currentImage = evt.target.result;
                    attachBtn.style.color = 'cyan';
                };
                reader.readAsDataURL(e.target.files[0]);
            }
        };

        // Override sendMessage to include image
        async function sendMessage() {
            const msg = chatInput.value.trim();
            if ((!msg && !currentImage) || !currentAgent) return;

            addMessage(msg, 'user', currentImage);
            chatInput.value = '';
            const imgToSend = currentImage;
            currentImage = null;
            attachBtn.style.color = 'inherit';
            fileInput.value = '';

            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        project_name: projectName,
                        agent_role: currentAgent.role,
                        message: msg,
                        image_data: imgToSend
                    })
                });
                const data = await res.json();
                if (data.reply) {
                    addMessage(data.reply, 'agent');
                    if (window.speakCheck) window.speakCheck(data.reply);
                }
            } catch (e) { addMessage('Error', 'agent'); }
        }

        closeChatBtn.onclick = () => {
            chatSection.classList.add('hidden');
        };
    }

    // --- Git Control ---
    const gitBtn = document.createElement('button');
    gitBtn.innerHTML = '🐙';
    gitBtn.className = 'icon-btn';
    gitBtn.title = "Git Control";
    document.querySelector('.header-actions').appendChild(gitBtn);

    gitBtn.onclick = async () => {
        // Show Modal (assumed existing or create it)
        let modal = document.getElementById('gitModal');
        if (!modal) {
            alert("Please ensure Git Modal HTML is present.");
            return;
        }
        modal.classList.remove('hidden');

        // Initial Load
        // We need project name.
        // Try to grab from projectInfo or URL
        const projName = document.querySelector('.project-title')?.textContent;
        if (projName) {
            document.getElementById('gitInitBtn').onclick = () => fetch('/api/git/init', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_name: projName })
            }).then(() => alert("Repo Initialized"));
        }
    };

    // --- Test Runner ---
    const testBtn = document.createElement('button');
    testBtn.innerHTML = '🧪';
    testBtn.className = 'icon-btn';
    testBtn.title = "Test Runner";
    document.querySelector('.header-actions').appendChild(testBtn);

    testBtn.onclick = () => {
        document.getElementById('testModal').classList.remove('hidden');
        const projName = document.querySelector('.project-title')?.textContent;
        const outputPre = document.getElementById('testOutput');
        const dbgActions = document.getElementById('debugActions');

        if (projName) {
            document.getElementById('runTestsBtn').onclick = async () => {
                outputPre.textContent = "Running tests...";
                dbgActions.classList.add('hidden');

                try {
                    const res = await fetch('/api/test/run', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ project_name: projName })
                    });
                    const data = await res.json();
                    outputPre.textContent = data.output;

                    if (data.exit_code !== 0) {
                        // Show Auto-Fix
                        dbgActions.classList.remove('hidden');

                        // Auto Fix Logic
                        document.getElementById('autoFixBtn').onclick = async () => {
                            const btn = document.getElementById('autoFixBtn');
                            btn.disabled = true;
                            btn.textContent = "✨ AI Fixing...";

                            try {
                                const fixRes = await fetch('/api/debug', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        project_name: projName,
                                        error_log: data.output
                                    })
                                });
                                const fixData = await fixRes.json();
                                if (fixData.status === "fixed") {
                                    alert("Fixed! " + fixData.message + "\nAI Thought: " + fixData.thought);
                                    // Re-run
                                    document.getElementById('runTestsBtn').click();
                                } else {
                                    alert("Fix failed: " + fixData.message);
                                }
                            } catch (e) { alert("Debug Error: " + e.message); }
                            finally {
                                btn.disabled = false;
                                btn.textContent = "✨ Auto-Fix with AI";
                            }
                        };
                    }

                } catch (e) {
                    outputPre.textContent = "Error: " + e.message;
                }
            };
        }
    };

    // Monetization Logic
    checkUserStatus();

    async function checkUserStatus() {
        try {
            const res = await fetch('/api/user-status');
            const data = await res.json();

            const adBar = document.getElementById('adBar');
            const daysLeftSpan = document.getElementById('daysLeft');
            const upgradeBtn = document.getElementById('upgradeBtn');
            const subModal = document.getElementById('subModal');
            const closeSub = document.querySelector('.close-sub');

            if (!data.is_subscribed) {
                // Show Ad Bar
                adBar.classList.remove('hidden');
                daysLeftSpan.textContent = data.days_left;

                // Modal Logic
                upgradeBtn.onclick = () => subModal.classList.remove('hidden');
                closeSub.onclick = () => subModal.classList.add('hidden');

                // Init PayPal
                initPayPal(subModal);
            } else {
                adBar.classList.add('hidden');
            }
        } catch (e) {
            console.error("Status check failed", e);
        }
    }

    function initPayPal(modal) {
        if (document.getElementById('paypal-button-container').children.length > 0) return;

        paypal.Buttons({
            style: {
                shape: 'rect',
                color: 'gold',
                layout: 'vertical',
                label: 'subscribe'
            },
            createSubscription: function (data, actions) {
                return actions.subscription.create({
                    'plan_id': 'P-2UP63371C2503224KMF7I66Y' // Sandbox Plan ID
                });
            },
            onApprove: function (data, actions) {
                // Determine subscriptionID
                console.log(data);

                // Capture/Verify on backend
                fetch('/api/subscribe/capture', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        subscriptionID: data.subscriptionID
                    })
                }).then(res => {
                    if (res.ok) {
                        alert('Subscription Successful! Welcome to Pro.');
                        modal.classList.add('hidden');
                        document.getElementById('adBar').classList.add('hidden');
                    }
                });
            }
        }).render('#paypal-button-container');
    }

    // --- Audio / ElevenLabs Logic ---
    const elevenKeyInput = document.getElementById('elevenKey');
    const voiceSelect = document.getElementById('voiceSelect');
    const narratorToggle = document.getElementById('narratorToggle');
    const saveAudioBtn = document.getElementById('saveAudioBtn');

    // Load Saved Settings
    if (localStorage.getItem('elevenKey')) elevenKeyInput.value = localStorage.getItem('elevenKey');
    if (localStorage.getItem('voiceId')) voiceSelect.value = localStorage.getItem('voiceId');
    if (localStorage.getItem('narratorMode') === 'true') narratorToggle.checked = true;

    // Fetch Voices on Load (if key exists)
    if (elevenKeyInput.value) fetchVoices();

    saveAudioBtn.addEventListener('click', () => {
        localStorage.setItem('elevenKey', elevenKeyInput.value);
        localStorage.setItem('voiceId', voiceSelect.value);
        localStorage.setItem('narratorMode', narratorToggle.checked);
        alert('Audio settings saved!');
        if (elevenKeyInput.value) fetchVoices();
    });

    async function fetchVoices() {
        try {
            const key = elevenKeyInput.value;
            const res = await fetch('/api/voices', {
                headers: { 'X-ElevenLabs-Key': key }
            });
            const data = await res.json();
            if (data.voices) {
                voiceSelect.innerHTML = ''; // clear defaults
                data.voices.forEach(v => {
                    const opt = document.createElement('option');
                    opt.value = v.voice_id;
                    opt.textContent = v.name;
                    voiceSelect.appendChild(opt);
                });
                // Restore selection
                if (localStorage.getItem('voiceId')) voiceSelect.value = localStorage.getItem('voiceId');
            }
        } catch (e) { console.error("Error fetching voices", e); }
    }

    // Global Speak Function (Replace Browser TTS)
    // We override the one inside initChat or define a global one.
    // Ideally we define this on window or pass it down.
    // For now, let's attach to window to be accessible everywhere including status updates.
    window.speakCheck = async function (text, forceShort = false) {
        if (!narratorToggle.checked) return;

        // Summarization for "Quick Guidance"
        let textToRead = text;
        if (text.length > 200 || forceShort) {
            // Dumb Summary: First sentence only.
            // Improve: Use an Agent to summarize? Expensive.
            // Let's split by period.
            const sentences = text.split(/[.!?]/);
            textToRead = sentences[0] + ". " + (sentences[1] || "") + "...";
        }

        const key = elevenKeyInput.value;
        const voiceId = voiceSelect.value;

        // If no ElevenLabs Key, fallback to browser? 
        // User asked for ElevenLabs specifically. 
        // Let's try API if key exists, else Browser.

        if (key || true) { // Try API (Server might have Env Key)
            try {
                const res = await fetch('/api/tts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-ElevenLabs-Key': key
                    },
                    body: JSON.stringify({ text: textToRead, voice_id: voiceId })
                });

                if (res.ok) {
                    const blob = await res.blob();
                    const url = URL.createObjectURL(blob);
                    const audio = new Audio(url);
                    audio.play();
                    return;
                }
            } catch (e) { console.error("TTS API Failed", e); }
        }

        // Fallback
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(textToRead);
            window.speechSynthesis.speak(utterance);
        }
    };

    // --- Mentor Polling Loop ---
    setInterval(async () => {
        // Only if narrator/auto-guidance is on? Or maybe separate "Mentor" toggle?
        // User asked for "Mentor" mode. Let's assume it shares the 'Narrator Mode' toggle or is always active if narrator on.
        const narratorOn = document.getElementById('narratorToggle').checked;
        if (!narratorOn) return;

        // Get Project Name from page state (might be in data obj if defined nearby, or grab from DOM)
        // We need a stable way to get current project.
        // Let's assume 'projectName' var from initChat scope is hard to reach here.
        // But we have 'projectInfo.innerHTML' or URL param.
        const urlParams = new URLSearchParams(window.location.search);
        const urlProject = urlParams.get('project');
        // Fallback to title
        const domProject = document.querySelector('.project-title') ? document.querySelector('.project-title').textContent : null;
        const activeProject = urlProject || domProject || "Untitled";

        if (!activeProject || activeProject === "Untitled") return;

        try {
            const res = await fetch(`/api/mentor/tip?project_name=${encodeURIComponent(activeProject)}`);
            const data = await res.json();

            if (data.tip) {
                // Play it!
                console.log("Mentor Tip:", data.tip);
                // Slight delay or visual cue?
                // Just speak it.
                if (window.speakCheck) window.speakCheck(data.tip);

                // Optional: Show a toast "Mentor Tip: ..."
            }
        } catch (e) {
            console.error("Mentor Poll Error", e);
        }
    }, 45000); // Poll every 45s

});
