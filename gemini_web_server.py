#!/usr/bin/env python3
import os
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, send_file
import google.generativeai as genai
from datetime import datetime
import threading

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("ERROR: GEMINI_API_KEY not found in .env")
    exit(1)

genai.configure(api_key=api_key)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Store results in memory
results_cache = {}
current_status = {"status": "idle", "message": ""}

class GeminiAgent:
    def __init__(self, name, system_prompt):
        self.name = name
        self.system_prompt = system_prompt
        self.model = genai.GenerativeModel('gemini-3.8-flash')
    
    def run(self, task, context=""):
        if context:
            prompt = f"{self.system_prompt}\n\nContext:\n{context}\n\nTask: {task}"
        else:
            prompt = f"{self.system_prompt}\n\nTask: {task}"
        
        try:
            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                )
            )
            return response.text
        except Exception as e:
            raise Exception(f"Error in {self.name}: {str(e)}")

def run_agents(user_request, project_name):
    """Run all agents and store results"""
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
        
        # Research
        current_status = {"status": "running", "message": "🔍 Running Research Agent..."}
        research_output = agents["research"].run(user_request)
        results["research"] = research_output
        
        # Analysis
        current_status = {"status": "running", "message": "📊 Running Analysis Agent..."}
        analysis_output = agents["analysis"].run("Analyze the research", context=research_output[:800])
        results["analysis"] = analysis_output
        
        # Development
        current_status = {"status": "running", "message": "🏗️ Running Development Agent..."}
        development_output = agents["development"].run("Create development plan", context=analysis_output[:800])
        results["development"] = development_output
        
        # Coding
        current_status = {"status": "running", "message": "💻 Running Coding Agent..."}
        coding_output = agents["coding"].run("Write the code", context=development_output[:800])
        results["coding"] = coding_output
        
        # QA
        current_status = {"status": "running", "message": "✅ Running QA Agent..."}
        qa_output = agents["qa"].run("Review and provide feedback", context=coding_output[:800])
        results["qa"] = qa_output
        
        # Save to disk
        os.makedirs(f"projects/{project_name}", exist_ok=True)
        for name, output in results.items():
            with open(f"projects/{project_name}/{name}.md", "w") as f:
                f.write(f"# {name.upper()} Agent Output\n\n{output}")
        
        # Store in cache
        results_cache[project_name] = {
            "request": user_request,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "results": results
        }
        
        current_status = {"status": "complete", "message": "✅ Workflow Complete!"}
        return results
    
    except Exception as e:
        current_status = {"status": "error", "message": f"❌ Error: {str(e)}"}
        raise

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.route('/api/status')
def status():
    """Get current status"""
    return jsonify(current_status)

@app.route('/api/process', methods=['POST'])
def process():
    """Process a request through all agents"""
    data = request.json
    user_request = data.get('request', '')
    project_name = data.get('project_name', 'project_' + datetime.now().strftime("%Y%m%d_%H%M%S"))
    
    if not user_request:
        return jsonify({"error": "Please enter a request"}), 400
    
    try:
        # Run in background thread
        def run_in_thread():
            run_agents(user_request, project_name)
        
        thread = threading.Thread(target=run_in_thread)
        thread.start()
        
        return jsonify({
            "status": "processing",
            "project_name": project_name,
            "message": "Processing started..."
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/results/<project_name>')
def get_results(project_name):
    """Get results for a project"""
    if project_name in results_cache:
        return jsonify(results_cache[project_name])
    
    # Try to load from disk
    try:
        results = {}
        for agent in ["research", "analysis", "development", "coding", "qa"]:
            filepath = f"projects/{project_name}/{agent}.md"
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    results[agent] = f.read()
        
        if results:
            return jsonify({"results": results})
        return jsonify({"error": "Project not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/projects')
def list_projects():
    """List all projects"""
    projects = []
    if os.path.exists("projects"):
        for project in os.listdir("projects"):
            project_path = os.path.join("projects", project)
            if os.path.isdir(project_path):
                files = os.listdir(project_path)
                projects.append({
                    "name": project,
                    "agents": len(files),
                    "files": files
                })
    # FIXED: Sort by project name properly
    return jsonify({"projects": sorted(projects, key=lambda x: x['name'], reverse=True)})

@app.route('/api/download/<project_name>')
def download_project(project_name):
    """Download project as ZIP"""
    try:
        results = {}
        for agent in ["research", "analysis", "development", "coding", "qa"]:
            filepath = f"projects/{project_name}/{agent}.md"
            if os.path.exists(filepath):
                with open(filepath, "r") as f:
                    results[agent] = f.read()
        
        # Create ZIP with all files
        import zipfile
        from io import BytesIO
        
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for agent, content in results.items():
                zip_file.writestr(f"{agent}.md", content)
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{project_name}.zip'
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("Starting Multi-Agent AI Web Server...")
    print("Open your browser to: http://localhost:5000")
    app.run(debug=True, port=5000)
