from rest_framework import serializers

class CommandSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["set_repo", "change_repo", "reset_repo", "run"])
    command = serializers.CharField(required=False, allow_blank=True)
    repo_url = serializers.URLField(required=False)
