from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import CommandSerializer
from .agent_handler import process_github_command

class GitHubCommandAPIView(APIView):
    def post(self, request):
        serializer = CommandSerializer(data=request.data)
        if serializer.is_valid():
            command = serializer.validated_data['command']
            try:
                result = process_github_command(command)
                return Response({"result": result}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
