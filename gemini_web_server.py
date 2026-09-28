#!/usr/bin/env python3
import os, re, zipfile, threading
from io import BytesIO
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env"); exit(1)
genai.configure(api_key=api_key)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

results_cache = {}
current_status = {"status": "idle", "message": ""}
TEXT_EXTENSIONS = {".md",".txt",".py",".js",".ts",".tsx",".jsx",".json",".html",".css",".yml",".yaml",".toml",".csv",".env",".sh",".rs",".go",".java",".c",".cpp",".h",".rb",".php",".sql",".xml",".svg"}
MAX_UPLOAD_CONTEXT_BYTES = 80 * 1024
SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\-]+")

def sanitize_filename(name):
    cleaned = SAFE_NAME_RE.sub("_", os.path.basename(name or "file")).strip("._")
    return cleaned or "file"

def sanitize_project_name(name):
    cleaned = SAFE_NAME_RE.sub("_", (name or "").strip()).strip("._")
    return cleaned or ("project_" + datetime.now().strftime("%Y%m%d_%H%M%S"))

def project_dir(project_name):
    return Path("projects") / project_name

def uploads_dir(project_name):
    return project_dir(project_name) / "uploads"

def list_upload_files(project_name):
    up = uploads_dir(project_name)
    if not up.is_dir():
        return []
    return [{"name": p.name, "size": p.stat().st_size} for p in sorted(up.iterdir()) if p.is_file()]

def save_uploaded_files(project_name, files):
    if not files:
        return []
    dest = uploads_dir(project_name)
    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        if not f or not getattr(f, "filename", None):
            continue
        fname = sanitize_filename(f.filename)
        target = dest / fname
        if target.exists():
            stem, suf, n = target.stem, target.suffix, 1
            while target.exists():
                target = dest / f"{stem}_{n}{suf}"; n += 1
            fname = target.name
        f.save(str(target))
        saved.append({"name": fname, "size": target.stat().st_size})
    return saved

def build_upload_context(project_name):
    uploads = list_upload_files(project_name)
    if not uploads:
        return "", ""
    summary = "Uploaded files:\n" + "\n".join(f"- {u['name']} ({u['size']} bytes)" for u in uploads)
    parts = ["## Uploaded file context\n", summary, "\n"]
    remaining = MAX_UPLOAD_CONTEXT_BYTES
    up = uploads_dir(project_name)
    for u in uploads:
        path = up / u["name"]
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            parts.append(f"\n### {u['name']}\n(Binary/unknown type, {u['size']} bytes — content omitted)\n")
            continue
        try:
            raw = path.read_bytes()
            try: text = raw.decode("utf-8")
            except UnicodeDecodeError: text = raw.decode("utf-8", errors="replace")
            if remaining <= 0:
                parts.append(f"\n### {u['name']}\n(Content truncated — context budget exhausted)\n")
                continue
            encoded = text.encode("utf-8")
            if len(encoded) > remaining:
                truncated = encoded[:remaining].decode("utf-8", errors="ignore")
                parts.append(f"\n### {u['name']}\n```\n{truncated}\n```\n(truncated)\n")
                remaining = 0
            else:
                parts.append(f"\n### {u['name']}\n```\n{text}\n```\n")
                remaining -= len(encoded)
        except Exception as e:
            parts.append(f"\n### {u['name']}\n(Could not read file: {e})\n")
    return "".join(parts), summary

class GeminiAgent:
    def __init__(self, name, system_prompt):
        self.name = name
        self.system_prompt = system_prompt
        self.model = genai.GenerativeModel('gemini-3.8-flash')
    def run(self, task, context=""):
        prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nTask: {task}" if context else f"{self.system_prompt}\n\nTask: {task}"
        try:
            response = self.model.generate_content(prompt, generation_config=genai.types.GenerationConfig(max_output_tokens=2048, temperature=0.7))
            return response.text
        except Exception as e:
            raise Exception(f"Error in {self.name}: {str(e)}")

def run_agents(user_request, project_name, upload_summary=""):
    global current_status
    try:
        agents = {
            "research": GeminiAgent("research", "You are a Research Agent. Gather information and best practices."),
            "analysis": GeminiAgent("analysis", "You are an Analysis Agent. Analyze findings and provide insights."),
            "development": GeminiAgent("development", "You are a Development Agent. Plan architecture and solution."),
            "coding": GeminiAgent("coding", "You are a Coding Agent. Write complete, production-ready code."),
            "qa": GeminiAgent("qa", "You are a QA Agent. Review code and ensure quality."),
        }
        results = {}
        upload_context, _ = build_upload_context(project_name)
        summary_note = upload_summary or ""
        if not summary_note and upload_context:
            _, summary_note = build_upload_context(project_name)

        current_status = {"status": "running", "message": "🔍 Running Research Agent..."}
        research_task = f"{user_request}\n\n{upload_context}" if upload_context else user_request
        results["research"] = agents["research"].run(research_task)

        def with_uploads(ctx):
            return f"{summary_note}\n\n{ctx}" if summary_note else ctx

        current_status = {"status": "running", "message": "📊 Running Analysis Agent..."}
        results["analysis"] = agents["analysis"].run("Analyze the research", context=with_uploads(results["research"][:800]))
        current_status = {"status": "running", "message": "🏗️ Running Development Agent..."}
        results["development"] = agents["development"].run("Create development plan", context=with_uploads(results["analysis"][:800]))
        current_status = {"status": "running", "message": "💻 Running Coding Agent..."}
        results["coding"] = agents["coding"].run("Write the code", context=with_uploads(results["development"][:800]))
        current_status = {"status": "running", "message": "✅ Running QA Agent..."}
        results["qa"] = agents["qa"].run("Review and provide feedback", context=with_uploads(results["coding"][:800]))

        os.makedirs(f"projects/{project_name}", exist_ok=True)
        for name, output in results.items():
            with open(f"projects/{project_name}/{name}.md", "w") as f:
                f.write(f"# {name.upper()} Agent Output\n\n{output}")

        results_cache[project_name] = {
            "request": user_request,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results,
            "uploads": list_upload_files(project_name),
        }
        current_status = {"status": "complete", "message": "✅ Workflow Complete!"}
        return results
    except Exception as e:
        current_status = {"status": "error", "message": f"❌ Error: {str(e)}"}
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    return jsonify(current_status)

@app.route('/api/process', methods=['POST'])
def process():
    uploaded = []
    if request.content_type and "multipart/form-data" in request.content_type:
        user_request = (request.form.get("request") or "").strip()
        project_name = sanitize_project_name(request.form.get("project_name") or ("project_" + datetime.now().strftime("%Y%m%d_%H%M%S")))
        uploaded = save_uploaded_files(project_name, request.files.getlist("files[]") or request.files.getlist("files"))
    else:
        data = request.get_json(silent=True) or {}
        user_request = (data.get("request") or "").strip()
        project_name = sanitize_project_name(data.get("project_name") or ("project_" + datetime.now().strftime("%Y%m%d_%H%M%S")))

    if not user_request:
        return jsonify({"error": "Please enter a request"}), 400

    existing = uploaded or list_upload_files(project_name)
    upload_summary = ("Uploaded files:\n" + "\n".join(f"- {u['name']} ({u['size']} bytes)" for u in existing)) if existing else ""

    try:
        threading.Thread(target=lambda: run_agents(user_request, project_name, upload_summary=upload_summary)).start()
        return jsonify({"status": "processing", "project_name": project_name, "message": "Processing started...", "uploads": existing})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/results/<project_name>')
def get_results(project_name):
    uploads = list_upload_files(project_name)
    if project_name in results_cache:
        payload = dict(results_cache[project_name]); payload["uploads"] = uploads
        return jsonify(payload)
    try:
        results = {}
        for agent in ["research", "analysis", "development", "coding", "qa"]:
            filepath = f"projects/{project_name}/{agent}.md"
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    results[agent] = f.read()
        if results or uploads:
            return jsonify({"results": results, "uploads": uploads})
        return jsonify({"error": "Project not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects')
def list_projects():
    projects = []
    if os.path.exists("projects"):
        for project in os.listdir("projects"):
            project_path = os.path.join("projects", project)
            if os.path.isdir(project_path):
                files = []
                for root, dirs, filenames in os.walk(project_path):
                    for fn in filenames:
                        files.append(os.path.relpath(os.path.join(root, fn), project_path).replace("\\", "/"))
                uploads = list_upload_files(project)
                agent_count = sum(1 for a in ["research", "analysis", "development", "coding", "qa"] if os.path.exists(os.path.join(project_path, f"{a}.md")))
                projects.append({"name": project, "agents": agent_count, "files": files, "uploads": uploads})
    return jsonify({"projects": sorted(projects, key=lambda x: x['name'], reverse=True)})

@app.route('/api/download/<project_name>')
def download_project(project_name):
    try:
        project_path = project_dir(project_name)
        if not project_path.is_dir():
            return jsonify({"error": "Project not found"}), 404
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for root, dirs, filenames in os.walk(project_path):
                for fn in filenames:
                    full = os.path.join(root, fn)
                    zip_file.write(full, arcname=os.path.relpath(full, project_path).replace("\\", "/"))
        zip_buffer.seek(0)
        return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name=f'{project_name}.zip')
    except Exception as e:
        return jsonify({"error": str(e)}), 500

from github_push import register_github_routes
register_github_routes(app, project_dir=project_dir, sanitize_project_name=sanitize_project_name)

if __name__ == '__main__':
    print("Starting Multi-Agent AI Web Server...")
    print("Open your browser to: http://localhost:5000")
    port = int(os.getenv("PORT", "5000"))
    app.run(debug=os.getenv("DEBUG", "False").lower() == "true", port=port, host="0.0.0.0")
