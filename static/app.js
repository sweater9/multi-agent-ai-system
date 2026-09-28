let currentProject = null;
let currentResults = {};
let attachedFiles = [];
let githubConnected = false;
const AGENT_ORDER = ['research', 'analysis', 'development', 'coding', 'qa'];
function escapeHtml(str) {
const amp = '&' + 'amp;';
const lt = '&' + 'lt;';
const gt = '&' + 'gt;';
return String(str).replace(/&/g, amp).replace(/</g, lt).replace(/>/g, gt);
}
function formatMarkdownLite(text) {
const escaped = escapeHtml(text || '');
return escaped
.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
.replace(/^### (.*)$/gm, '<strong>$1</strong>')
.replace(/^## (.*)$/gm, '<strong style="font-size:1.05em">$1</strong>')
.replace(/^# (.*)$/gm, '<strong style="font-size:1.15em">$1</strong>')
.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
.replace(/`([^`]+)`/g, '<code>$1</code>');
}
function formatBytes(n) {
if (n < 1024) return n + ' B';
if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
return (n / (1024 * 1024)).toFixed(1) + ' MB';
}
function showStatus(message, type) {
const el = document.getElementById('status');
const spinning = type === 'processing'
? '<span class="spinner" aria-hidden="true"></span>'
: '';
el.innerHTML = spinning + `<span></span>`;
el.querySelector('span:last-child').textContent = String(message || '').replace(/^[⏳❌✅]\s*/, '');
el.className = `status show ${type}`;
}
function resetPipeline() {
document.querySelectorAll('.step').forEach(step => {
step.classList.remove('active', 'done');
});
}
function updatePipelineFromMessage(message) {
const lower = (message || '').toLowerCase();
let active = null;
for (const agent of AGENT_ORDER) {
if (lower.includes(agent)) { active = agent; break; }
}
document.querySelectorAll('.step').forEach(step => {
const name = step.dataset.step;
step.classList.remove('active', 'done');
if (!active) return;
const idx = AGENT_ORDER.indexOf(name);
const activeIdx = AGENT_ORDER.indexOf(active);
if (idx < activeIdx) step.classList.add('done');
if (idx === activeIdx) step.classList.add('active');
});
}
function markPipelineComplete() {
document.querySelectorAll('.step').forEach(step => {
step.classList.remove('active');
step.classList.add('done');
});
}
/* ---- File attach ---- */
function renderFileList() {
const list = document.getElementById('fileList');
if (!attachedFiles.length) { list.innerHTML = ''; return; }
list.innerHTML = attachedFiles.map((f, i) => `
<li class="file-item">
<div class="meta">
<span class="name" title="${escapeHtml(f.name)}">${escapeHtml(f.name)}</span>
<span class="size">${formatBytes(f.size)}</span>
</div>
<button type="button" class="remove" data-idx="${i}" aria-label="Remove">✕</button>
</li>
`).join('');
list.querySelectorAll('.remove').forEach(btn => {
btn.addEventListener('click', (e) => {
e.stopPropagation();
attachedFiles.splice(Number(btn.dataset.idx), 1);
renderFileList();
});
});
}
function addFiles(fileList) {
const incoming = Array.from(fileList || []);
for (const f of incoming) {
if (attachedFiles.some(x => x.name === f.name && x.size === f.size)) continue;
attachedFiles.push(f);
}
renderFileList();
}
function setupDropzone() {
const zone = document.getElementById('dropzone');
const input = document.getElementById('fileInput');
zone.addEventListener('click', () => input.click());
zone.addEventListener('keydown', (e) => {
if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); input.click(); }
});
input.addEventListener('change', () => {
addFiles(input.files);
input.value = '';
});
zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
zone.addEventListener('drop', (e) => {
e.preventDefault();
zone.classList.remove('dragover');
addFiles(e.dataTransfer.files);
});
}
async function processRequest() {
const projectName = document.getElementById('projectName').value.trim()
|| ('project_' + new Date().toISOString().slice(0, 10).replace(/-/g, ''));
const userRequest = document.getElementById('userRequest').value.trim();
if (!userRequest) {
showStatus('Please enter a project description.', 'error');
return;
}
document.getElementById('projectName').value = projectName;
document.getElementById('processBtn').disabled = true;
resetPipeline();
showStatus('Starting workflow…', 'processing');
try {
let response;
if (attachedFiles.length > 0) {
const form = new FormData();
form.append('request', userRequest);
form.append('project_name', projectName);
attachedFiles.forEach(f => form.append('files[]', f, f.name));
response = await fetch('/api/process', { method: 'POST', body: form });
} else {
response = await fetch('/api/process', {
method: 'POST',
headers: { 'Content-Type': 'application/json' },
body: JSON.stringify({ request: userRequest, project_name: projectName })
});
}
const data = await response.json();
if (!response.ok) throw new Error(data.error || 'Request failed');
currentProject = projectName;
document.getElementById('activeProjectLabel').textContent = projectName;
let done = false;
let attempts = 0;
while (!done && attempts < 180) {
await new Promise(r => setTimeout(r, 2000));
const statusResponse = await fetch('/api/status');
const statusData = await statusResponse.json();
if (statusData.status === 'complete') {
showStatus(statusData.message || 'Workflow complete', 'complete');
markPipelineComplete();
await loadProjectResults(projectName);
done = true;
} else if (statusData.status === 'error') {
showStatus(statusData.message || 'Workflow failed', 'error');
done = true;
} else {
updatePipelineFromMessage(statusData.message || '');
showStatus(statusData.message || 'Processing…', 'processing');
}
attempts += 1;
}
if (!done) {
showStatus('Still running — refresh projects shortly.', 'processing');
}
await loadProjects();
} catch (error) {
showStatus(error.message, 'error');
} finally {
document.getElementById('processBtn').disabled = false;
}
}
async function loadProjectResults(projectName) {
try {
const response = await fetch(`/api/results/${encodeURIComponent(projectName)}`);
const data = await response.json();
if (!data.results) return;
currentProject = projectName;
currentResults = data.results;
document.getElementById('activeProjectLabel').textContent = projectName;
document.getElementById('projectName').value = projectName;
document.getElementById('noResults').style.display = 'none';
document.getElementById('resultsSection').style.display = 'block';
document.querySelectorAll('.project').forEach(el => {
el.classList.toggle('active', el.dataset.name === projectName);
});
const firstTab = document.querySelector('.tab[data-agent="research"]');
showResult('research', firstTab);
} catch (error) {
console.error('Error loading results:', error);
}
}
function showResult(agent, tabEl) {
document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
if (tabEl) tabEl.classList.add('active');
const content = currentResults[agent] || 'No output for this agent yet.';
document.getElementById('resultContent').innerHTML = formatMarkdownLite(content);
}
async function loadProjects() {
try {
const response = await fetch('/api/projects');
const data = await response.json();
const list = document.getElementById('projectsList');
if (!data.projects || data.projects.length === 0) {
list.innerHTML = '<div class="empty">No projects yet. Run your first workflow.</div>';
return;
}
list.innerHTML = data.projects.map(project => {
const uploadCount = (project.uploads && project.uploads.length) || 0;
const meta = uploadCount
? `${project.agents} agent outputs · ${uploadCount} upload${uploadCount === 1 ? '' : 's'}`
: `${project.agents} agent outputs`;
return `
<div class="project ${project.name === currentProject ? 'active' : ''}" data-name="${escapeHtml(project.name)}">
<div style="min-width:0">
<div class="project-name">${escapeHtml(project.name)}</div>
<div class="project-meta">${meta}</div>
</div>
<button class="btn btn-ghost" type="button">Open</button>
</div>`;
}).join('');
list.querySelectorAll('.project').forEach(el => {
el.addEventListener('click', () => loadProjectResults(el.dataset.name));
});
} catch (error) {
console.error('Error loading projects:', error);
document.getElementById('projectsList').innerHTML = '<div class="empty">Could not load projects.</div>';
}
}
function downloadProject(projectName) {
projectName = projectName || currentProject;
if (!projectName) return;
window.location.href = `/api/download/${encodeURIComponent(projectName)}`;
}
/* ---- GitHub ---- */
async function loadGitHubStatus() {
const badge = document.getElementById('ghBadge');
const text = document.getElementById('ghBadgeText');
const btn = document.getElementById('ghPushBtn');
try {
const res = await fetch('/api/github/status');
const data = await res.json();
githubConnected = !!data.connected;
if (githubConnected) {
badge.className = 'gh-badge connected';
text.textContent = data.username ? `Connected as ${data.username}` : 'Connected';
btn.disabled = false;
if (data.username && !document.getElementById('ghRepo').value) {
document.getElementById('ghRepo').placeholder = `${data.username}/repo-name`;
}
} else {
badge.className = 'gh-badge disconnected';
text.textContent = 'Not connected';
btn.disabled = true;
document.getElementById('ghMsg').textContent =
'Set GITHUB_TOKEN and GITHUB_USERNAME on the server to enable push.';
}
} catch (e) {
badge.className = 'gh-badge disconnected';
text.textContent = 'Unavailable';
btn.disabled = true;
}
}
async function pushToGitHub() {
const msgEl = document.getElementById('ghMsg');
const btn = document.getElementById('ghPushBtn');
const projectName = (document.getElementById('projectName').value.trim() || currentProject || '').trim();
const repo = document.getElementById('ghRepo').value.trim();
const branch = document.getElementById('ghBranch').value.trim() || 'main';
const message = document.getElementById('ghMessage').value.trim();
if (!projectName) {
msgEl.className = 'gh-msg error';
msgEl.textContent = 'Select or name a project first.';
return;
}
if (!repo) {
msgEl.className = 'gh-msg error';
msgEl.textContent = 'Enter owner/repo (or a repo name under your GitHub username).';
return;
}
if (!githubConnected) {
msgEl.className = 'gh-msg error';
msgEl.textContent = 'GitHub is not connected on the server.';
return;
}
btn.disabled = true;
msgEl.className = 'gh-msg';
msgEl.textContent = 'Pushing…';
try {
const res = await fetch('/api/github/push', {
method: 'POST',
headers: { 'Content-Type': 'application/json' },
body: JSON.stringify({
project_name: projectName,
repo,
branch,
message: message || undefined,
}),
});
const data = await res.json();
if (!res.ok || !data.ok) {
msgEl.className = 'gh-msg error';
msgEl.textContent = data.error || 'Push failed';
return;
}
msgEl.className = 'gh-msg ok';
msgEl.innerHTML = `Pushed ${data.pushed || ''} file(s). <a href="${escapeHtml(data.url)}" target="_blank" rel="noopener">Open on GitHub</a>`;
} catch (e) {
msgEl.className = 'gh-msg error';
msgEl.textContent = e.message || 'Push failed';
} finally {
btn.disabled = !githubConnected;
}
}
window.addEventListener('load', () => {
setupDropzone();
loadProjects();
loadGitHubStatus();
});
