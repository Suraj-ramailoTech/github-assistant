import requests
import os

class GetRepositoryTool:
    name = "get_repository"

    def __init__(self):
        # Get token from env (same as your MCP server token)
        self.token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        if not self.token:
            raise ValueError("Missing GITHUB_PERSONAL_ACCESS_TOKEN")

    def run(self, owner: str, repo: str):
        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github+json"
        }
        url = f"https://api.github.com/repos/{owner}/{repo}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 404:
            return {"error": "Repository not found"}
        elif resp.status_code == 403:
            return {"error": "Forbidden - check token permissions"}
        else:
            return {"error": f"GitHub API error {resp.status_code}: {resp.text}"}
