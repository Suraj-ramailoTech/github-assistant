from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CommandSerializer
from .agent_handler import process_github_command
import json
import re

# TEMP in-memory store for repository context per user (replace with DB or cache in production)
REPO_CONTEXTS = {}

class GitHubCommandAPIView(APIView):
    def post(self, request):
        serializer = CommandSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_id = str(request.user.id) if request.user.is_authenticated else "anonymous"
        action = serializer.validated_data.get("action")
        command = serializer.validated_data.get("command", "")
        repo_url = serializer.validated_data.get("repo_url", "")

        try:
            if user_id not in REPO_CONTEXTS:
                REPO_CONTEXTS[user_id] = {"owner": None, "repo": None}

            # Handle repo setup/change/reset actions
            if action == "set_repo" or action == "change_repo":
                if not repo_url:
                    return Response({"error": "Missing repository URL"}, status=status.HTTP_400_BAD_REQUEST)
                result = process_github_command(f"change repo to {repo_url}", user_id, REPO_CONTEXTS)
                return Response(result, status=status.HTTP_200_OK)

            elif action == "reset_repo":
                result = process_github_command("reset repository", user_id, REPO_CONTEXTS)
                return Response(result, status=status.HTTP_200_OK)

            elif action == "run":
                if not command:
                    return Response({"error": "Missing command"}, status=status.HTTP_400_BAD_REQUEST)
                result = process_github_command(command, user_id, REPO_CONTEXTS)
                return Response(self.parse_json_from_raw(result.raw), status=status.HTTP_200_OK)

            else:
                return Response({"error": "Invalid action type."}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)\

    def parse_json_from_raw(self,raw_str: str) -> dict:
        """
        Cleans and parses a raw string (e.g. from CrewAI) into a valid JSON dict.
        Handles markdown code fences and leading/trailing whitespace.
        """
        # Strip leading/trailing whitespace
        raw_str = raw_str.strip()

        # Remove markdown-style code block (e.g. ```json ... ```)
        if raw_str.startswith("```"):
            raw_str = re.sub(r"^```(?:json)?\n?", "", raw_str)
            raw_str = re.sub(r"\n?```$", "", raw_str)

        # Parse JSON
        return json.loads(raw_str)
