"""
Serializers for the OAuth 2.0 / OIDC app.
"""

from rest_framework import serializers
from .models import OAuthClient


class OAuthClientSerializer(serializers.ModelSerializer):
    """Read serializer — never exposes the client secret."""

    class Meta:
        model = OAuthClient
        fields = [
            "client_id",
            "name",
            "agent_type",
            "redirect_uris",
            "is_active",
            "client_secret_prefix",
            "created_at",
        ]
        read_only_fields = fields


class OAuthClientCreateSerializer(serializers.Serializer):
    """Input for creating a new OAuth client."""

    name = serializers.CharField(max_length=100)
    agent_type = serializers.ChoiceField(choices=["mark", "hr"])
    redirect_uris = serializers.ListField(
        child=serializers.URLField(),
        min_length=1,
        help_text="At least one redirect URI is required.",
    )


class OAuthClientUpdateSerializer(serializers.ModelSerializer):
    """Partial update — only these fields are editable."""

    class Meta:
        model = OAuthClient
        fields = ["name", "redirect_uris", "is_active"]


class AuthorizeSerializer(serializers.Serializer):
    """Input for POST /oauth/authorize/"""

    client_id = serializers.UUIDField()
    redirect_uri = serializers.URLField()
    scope = serializers.CharField(default="openid profile", required=False)
    state = serializers.CharField(required=False, default="", allow_blank=True)


class TokenSerializer(serializers.Serializer):
    """Input for POST /oauth/token/"""

    grant_type = serializers.ChoiceField(choices=["authorization_code"])
    code = serializers.CharField()
    client_id = serializers.UUIDField()
    client_secret = serializers.CharField()
    redirect_uri = serializers.URLField()
