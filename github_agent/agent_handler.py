# from crewai_tools import MCPServerAdapter
# from crewai import Agent, Task, Crew
# from dotenv import load_dotenv
# from mcp import StdioServerParameters
# import os

# load_dotenv()

# def process_github_command(user_command: str) -> str:
#     token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
#     if not token:
#         raise ValueError("Missing GitHub token")

#     server_params = StdioServerParameters(
#         command="docker",
#         args=[
#             "run", "-i", "--rm",
#             "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
#             "ghcr.io/github/github-mcp-server"
#         ],
#         env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token}
#     )

#     with MCPServerAdapter(server_params) as github_tools:
#         print("\n\n\nGithub tools: ", [tool.name for tool in github_tools],"\n\n")
#         agent = Agent(
#         role="GitHub Automation Expert",
#         goal="Use the provided tools to perform GitHub operations as requested by the user. These operations may include managing repositories, issues, pull requests, branches, and other resources.",
#         backstory=(
#             "You are a GitHub automation agent integrated with the GitHub MCP server. "
#             "You use the provided GitHub API tools to execute actions like creating issues, "
#             "reviewing pull requests, listing branches, or modifying repositories. "
#             "You should interpret the user's command and use the correct tools to complete the task effectively. "
#             "CRITICAL: You must validate every response and only report success when operations actually succeed. "
#             "Check for error fields like 'error', 'message', or HTTP status codes >= 400 in responses. "
#             "Do NOT just return user profile information unless specifically requested. Always perform the actual requested action."
#         ),
#         tools=github_tools,
#         verbose=True
#         )

#         task = Task(
#     description=(
#         "Interpret the following user request and use the available GitHub tools to perform the necessary actions. "
#         f"User request: {user_command} "
#         "Strict Instructions: "
#         "1. ANALYZE the user command first to identify the PRIMARY ACTION requested. "
#         "2. SELECT the tool that directly matches the primary action - do not use unrelated tools. "
#         "3. Use repositories associated with the authenticated user only. "
#         "4. After EVERY tool execution, validate the response for success/failure. "
#         "5. Check responses for error indicators: 'error', 'message', 'failed', 'not found', 'forbidden'. "
#         "6. Only report SUCCESS if the operation actually succeeded with expected data. "
#         "7. Report the actual error message if any operation fails. "
#         "8. Do NOT claim success when the response contains error fields. "
#         "9. Return errors in the same format as success responses. "
#         "10. Get owner/profile information ONLY if required for the specific operation, not as the final result. "
#         "11. Always filter results to show ONLY resources owned by or directly associated with the authenticated user. "
#         "12. Verify ownership using 'owner.login' field matches authenticated user before returning results. "
#         "13. Use user-specific API endpoints when available instead of general search endpoints. "
#         "14. Return results in proper JSON format. "
#         "15. PERFORM EXACTLY what is requested - if asked for repositories, return repositories; if asked to delete PR, delete PR; if asked for issues, return issues. "
#         "16. Do NOT default to repository listing unless specifically asked for repositories."
#     ),
#     agent=agent,
#     expected_output="The result of the GitHub operation(s) with accurate success/failure status and any error messages in proper JSON format."
# )


#         crew = Crew(
#             agents=[agent],
#             tasks=[task],
#             verbose=True
#         )

#         return crew.kickoff()

import os
import re
from dotenv import load_dotenv
from crewai_tools import MCPServerAdapter
from crewai import Agent, Task, Crew
from mcp import StdioServerParameters
from .custom_tool import GetRepositoryTool
import json

load_dotenv()

def get_tool_by_name(tools, tool_name):
    for tool in tools:
        if getattr(tool, "name", None) == tool_name:
            return tool
    return None


def parse_repo_url(repo_url: str):
    """Parse GitHub repo URL and return (owner, repo)"""
    pattern = r"https://github.com/([^/]+)/([^/]+?)(?:\.git)?/?$"
    match = re.match(pattern, repo_url.strip())
    if not match:
        raise ValueError("Invalid GitHub repository URL format.")
    return match.group(1), match.group(2)

def validate_and_set_repo(owner: str, repo: str, github_tools, repo_context: dict) -> dict:
    """Validate repo ownership and update context"""
    me_tool = get_tool_by_name(github_tools, "get_me")
    if me_tool is None:
        return {"status": "error", "error": "get_me tool not found"}

    me_result = me_tool.run()
    me_result = json.loads(me_result) if isinstance(me_result, str) else me_result
    login = me_result.get("login")
    if not login:
        return {"status": "error", "error": "Failed to retrieve authenticated user info."}

    # Use the custom GetRepositoryTool directly instead of searching in github_tools
    get_repo_tool = GetRepositoryTool()
    repo_result = get_repo_tool.run(owner=owner, repo=repo)

    if "error" in repo_result:
        return {"status": "error", "error": repo_result["error"]}

    if "owner" not in repo_result or repo_result["owner"]["login"] != login:
        return {
            "status": "error",
            "error": f"Repository '{owner}/{repo}' does not belong to the authenticated user."
        }

    repo_context["owner"] = owner
    repo_context["repo"] = repo
    return {"status": "success", "message": f"Repository context set to {owner}/{repo}."}

def process_github_command(user_command: str, user_id: str, context_store: dict) -> dict:
    repo_context = context_store[user_id]
    token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
    if not token:
        raise ValueError("Missing GitHub token")

    server_params = StdioServerParameters(
        command="docker",
        args=[
            "run", "-i", "--rm",
            "-e", "GITHUB_PERSONAL_ACCESS_TOKEN",
            "ghcr.io/github/github-mcp-server"
        ],
        env={**os.environ, "GITHUB_PERSONAL_ACCESS_TOKEN": token}
    )

    with MCPServerAdapter(server_params) as github_tools:
        # Reset repo
        if user_command.lower().strip() == "reset repository":
            repo_context["owner"] = None
            repo_context["repo"] = None
            return {"status": "success", "message": "Repository context reset. Please set a new repository."}

        # Change repo
        if user_command.lower().startswith("change repo to"):
            new_url = user_command[len("change repo to"):].strip()
            try:
                owner, repo = parse_repo_url(new_url)
                result = validate_and_set_repo(owner, repo, github_tools, repo_context)
                return result
            except Exception as e:
                return {"status": "error", "error": str(e)}

        # Repo context must be set for other commands
        if repo_context["owner"] is None or repo_context["repo"] is None:
            return {"status": "error", "error": "Repository context is not set. Please set the repository first."}

        # Setup agent
        agent = Agent(
            role="Repository-Specific GitHub Automation Agent",
            goal=(
                "Execute GitHub operations strictly within the user-provided repository only. "
                "Reject commands outside repository scope."
            ),
            backstory=(
                "You operate only within the specified GitHub repository. Validate and perform all actions "
                "using official GitHub MCP tools and return short structured JSON."
            ),
            tools=github_tools,
            verbose=True
        )

        def perform_repo_task():
            full_command = (
                f"Perform the following command on repository '{repo_context['owner']}/{repo_context['repo']}':\n"
                f"{user_command}\n\n"
                f"Repository owner: {repo_context['owner']}\n"
                f"Repository name: {repo_context['repo']}\n\n"
                "Rules:\n"
                "1. Do not operate outside this repository.\n"
                "2. Validate existence of resources before actions.\n"
                "3. Return shory JSON-formatted results with status and data or error."
            )
            return Task(
                description=full_command,
                agent=agent,
                expected_output="Short JSON result with status."
            )


        crew = Crew(
            agents=[agent],
            tasks=[perform_repo_task()],
            verbose=True
        )

        return crew.kickoff()
