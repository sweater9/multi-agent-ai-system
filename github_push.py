"""GitHub push connector for Multi-Agent AI System."""
import os
import base64
import requests
from pathlib import Path
from flask import request, jsonify

def register_github_routes(app, project_dir, sanitize_project_name):
    def _github_headers():
        return {
            "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN') or ''}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "multi-agent-ai-system",
        }

    def _parse_repo(repo_field):
        repo_field = (repo_field or "").strip().strip("/")
        if not repo_field:
            return None, None
        if "/" in repo_field:
            owner, name = repo_field.split("/", 1)
            return owner.strip(), name.strip()
        return (os.getenv("GITHUB_USERNAME") or "").strip() or None, repo_field

    def _github_get_repo(owner, name):
        return requests.get(f"https://api.github.com/repos/{owner}/{name}", headers=_github_headers(), timeout=30)

    def _github_create_repo(name):
        return requests.post(
            "https://api.github.com/user/repos",
            headers=_github_headers(),
            json={"name": name, "private": False, "auto_init": True, "description": "Pushed from Multi-Agent AI System"},
            timeout=30,
        )

    def _github_get_file_sha(owner, name, path, branch):
        r = requests.get(
            f"https://api.github.com/repos/{owner}/{name}/contents/{path}",
            headers=_github_headers(),
            params={"ref": branch},
            timeout=30,
        )
        return r.json().get("sha") if r.status_code == 200 else None

    def _github_put_file(owner, name, path, content_bytes, message, branch):
        payload = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": branch,
        }
        sha = _github_get_file_sha(owner, name, path, branch)
        if sha:
            payload["sha"] = sha
        return requests.put(
            f"https://api.github.com/repos/{owner}/{name}/contents/{path}",
            headers=_github_headers(),
            json=payload,
            timeout=60,
        )

    def _iter_project_files(project_name):
        root = project_dir(project_name)
        if not root.is_dir():
            return
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                full = Path(dirpath) / fn
                yield full.relative_to(root).as_posix(), full

    @app.route('/api/github/status')
    def github_status():
        token = os.getenv("GITHUB_TOKEN") or ""
        username = os.getenv("GITHUB_USERNAME") or None
        connected = bool(token.strip())
        return jsonify({"connected": connected, "username": username if connected else None})

    @app.route('/api/github/push', methods=['POST'])
    def github_push():
        token = (os.getenv("GITHUB_TOKEN") or "").strip()
        if not token:
            return jsonify({"ok": False, "error": "GitHub is not connected. Set GITHUB_TOKEN (and GITHUB_USERNAME) on the server."}), 400
        data = request.get_json(silent=True) or {}
        project_name = sanitize_project_name(data.get("project_name") or "")
        repo_field = data.get("repo") or ""
        branch = (data.get("branch") or "main").strip() or "main"
        message = (data.get("message") or f"Push {project_name} from Multi-Agent AI").strip()
        if not project_name or not project_dir(project_name).is_dir():
            return jsonify({"ok": False, "error": "Project not found"}), 404
        owner, name = _parse_repo(repo_field)
        if not owner or not name:
            return jsonify({"ok": False, "error": "Provide repo as owner/name, or set GITHUB_USERNAME and pass a repo name."}), 400
        repo_resp = _github_get_repo(owner, name)
        if repo_resp.status_code == 404:
            create_resp = _github_create_repo(name)
            if create_resp.status_code not in (200, 201):
                try:
                    detail = create_resp.json().get("message", create_resp.text)
                except Exception:
                    detail = create_resp.text
                return jsonify({"ok": False, "error": f"Repo {owner}/{name} does not exist and could not be created ({create_resp.status_code}: {detail}). Please create the repository on GitHub, then try again."}), 400
        elif repo_resp.status_code != 200:
            try:
                detail = repo_resp.json().get("message", repo_resp.text)
            except Exception:
                detail = repo_resp.text
            return jsonify({"ok": False, "error": f"Could not access repo {owner}/{name}: {repo_resp.status_code} {detail}"}), 400
        files = list(_iter_project_files(project_name))
        if not files:
            return jsonify({"ok": False, "error": "Project has no files to push"}), 400
        pushed, errors = 0, []
        for rel, full in files:
            remote_path = f"{project_name}/{rel}"
            try:
                r = _github_put_file(owner, name, remote_path, full.read_bytes(), message, branch)
                if r.status_code in (200, 201):
                    pushed += 1
                else:
                    try:
                        msg = r.json().get("message", r.text)
                    except Exception:
                        msg = r.text
                    errors.append(f"{remote_path}: {r.status_code} {msg}")
            except Exception as e:
                errors.append(f"{remote_path}: {e}")
        url = f"https://github.com/{owner}/{name}/tree/{branch}/{project_name}"
        if errors and pushed == 0:
            return jsonify({"ok": False, "error": "Push failed: " + "; ".join(errors[:5]), "url": f"https://github.com/{owner}/{name}"}), 500
        result = {"ok": True, "url": url, "pushed": pushed, "repo": f"{owner}/{name}", "branch": branch}
        if errors:
            result["warnings"] = errors[:5]
        return jsonify(result)
