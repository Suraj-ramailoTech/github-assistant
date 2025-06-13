from crewai_tools import MCPServerAdapter
from crewai import Agent, Task, Crew
from dotenv import load_dotenv
from mcp import StdioServerParameters
import os

load_dotenv()

def process_github_command(user_command: str) -> str:
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
        agent = Agent(
            role="GitHub Manager",
            goal="Manage GitHub repositories and operations",
            backstory="You are an expert GitHub automation agent.",
            tools=github_tools,
            max_iter=5,
            verbose=True
        )

        task = Task(
            description=user_command,
            agent=agent,
            expected_output="GitHub operation result"
        )

        crew = Crew(
            agents=[agent],
            tasks=[task],
            verbose=True
        )

        return crew.kickoff()
