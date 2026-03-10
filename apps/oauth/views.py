"""
OAuth 2.0 / OIDC views.

POST /oauth/authorize/   — Authenticated user → get redirect URL with auth code
POST /oauth/token/       — Agent backend (server-to-server) → exchange code for tokens
GET  /oauth/userinfo/    — Agent → get user profile from access token
"""

import uuid
from datetime import timedelta

import jwt as pyjwt
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.auth_app.models import UserProfile
from .models import OAuthClient, OAuthAuthorizationCode
from .serializers import AuthorizeSerializer, TokenSerializer


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def authorize_view(request):
    """
    POST /oauth/authorize/
    Requires user authentication (Supabase JWT in Authorization header).

    Checks:
    - Client exists and is active
    - redirect_uri is registered for this client
    - User has an active subscription for the agent type

    Returns { redirect_url } — the frontend navigates the user there.
    Does NOT redirect directly (avoids CORS complications).
    """
    serializer = AuthorizeSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    data = serializer.validated_data
    user = request.user

    # Validate client
    try:
        client = OAuthClient.objects.get(client_id=data["client_id"], is_active=True)
    except OAuthClient.DoesNotExist:
        return Response({"success": False, "error": "Invalid client_id."}, status=400)

    # Validate redirect_uri
    if not client.is_redirect_uri_allowed(data["redirect_uri"]):
        return Response(
            {"success": False, "error": "redirect_uri not registered for this client."},
            status=400,
        )

    # Check user has access to this agent
    if client.agent_type == "mark" and not user.can_access_mark:
        return Response(
            {"success": False, "error": "No active subscription for MARK Agent."},
            status=403,
        )
    if client.agent_type == "hr" and not user.can_access_hr:
        return Response(
            {"success": False, "error": "No active subscription for HR Agent."},
            status=403,
        )

    # Generate and persist authorization code (10 min expiry)
    code = OAuthAuthorizationCode.generate_code()
    OAuthAuthorizationCode.objects.create(
        code=code,
        client=client,
        user=user,
        redirect_uri=data["redirect_uri"],
        scopes=data.get("scope", "openid profile"),
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    # Build redirect URL with code (and optional state for CSRF protection)
    state = data.get("state", "")
    redirect_url = f"{data['redirect_uri']}?code={code}"
    if state:
        redirect_url += f"&state={state}"

    return Response({"success": True, "data": {"redirect_url": redirect_url}})


@api_view(["POST"])
@permission_classes([])
@authentication_classes([])
def token_view(request):
    """
    POST /oauth/token/
    Public — called server-to-server by the agent backend (not the browser).

    Validates:
    - client_id + client_secret
    - authorization code (not expired, not already used, redirect_uri matches)

    Returns:
    - access_token: opaque UUID stored in cache (3600s TTL)
    - id_token: signed HS256 JWT containing user/tenant identity claims
    """
    serializer = TokenSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    data = serializer.validated_data

    # Validate client credentials
    try:
        client = OAuthClient.objects.get(client_id=data["client_id"], is_active=True)
    except OAuthClient.DoesNotExist:
        return Response({"success": False, "error": "Invalid client."}, status=401)

    if not client.verify_secret(data["client_secret"]):
        return Response({"success": False, "error": "Invalid client credentials."}, status=401)

    # Validate authorization code
    try:
        auth_code = OAuthAuthorizationCode.objects.select_related(
            "user", "user__tenant"
        ).get(code=data["code"], client=client)
    except OAuthAuthorizationCode.DoesNotExist:
        return Response({"success": False, "error": "Invalid authorization code."}, status=400)

    if not auth_code.is_valid():
        return Response(
            {"success": False, "error": "Authorization code expired or already used."},
            status=400,
        )

    if auth_code.redirect_uri != data["redirect_uri"]:
        return Response({"success": False, "error": "redirect_uri mismatch."}, status=400)

    # Mark code as used (single-use)
    auth_code.is_used = True
    auth_code.save(update_fields=["is_used"])

    user = auth_code.user
    tenant = user.tenant
    now = timezone.now()
    expiry_ts = int(now.timestamp()) + settings.OIDC_TOKEN_EXPIRY

    # Build OIDC id_token JWT
    id_token_claims = {
        "iss": settings.OIDC_ISSUER,
        "sub": str(user.id),
        "aud": str(client.client_id),
        "exp": expiry_ts,
        "iat": int(now.timestamp()),
        # User identity claims
        "email": user.email,
        "name": user.full_name,
        "picture": user.avatar_url,
        # SIA-specific claims
        "tenant_id": str(tenant.tenant_id) if tenant else None,
        "tenant_name": tenant.name if tenant else None,
        "agent_access": user.get_accessible_agents(),
    }

    id_token = pyjwt.encode(
        id_token_claims,
        settings.OIDC_SIGNING_KEY,
        algorithm="HS256",
    )

    # Generate opaque access_token, store in cache for userinfo lookups
    access_token = str(uuid.uuid4()).replace("-", "")
    cache.set(
        f"oauth_at:{access_token}",
        {"user_id": str(user.id), "client_id": str(client.client_id)},
        settings.OIDC_TOKEN_EXPIRY,
    )

    return Response({
        "access_token": access_token,
        "id_token": id_token,
        "token_type": "Bearer",
        "expires_in": settings.OIDC_TOKEN_EXPIRY,
    })


@api_view(["GET"])
@permission_classes([])
@authentication_classes([])
def userinfo_view(request):
    """
    GET /oauth/userinfo/
    Returns OIDC user profile for a valid OAuth access_token.
    Token passed as: Authorization: Bearer <access_token>
    """
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth_header.startswith("Bearer "):
        return Response({"error": "Missing or invalid bearer token."}, status=401)

    access_token = auth_header[7:].strip()
    token_data = cache.get(f"oauth_at:{access_token}")
    if not token_data:
        return Response({"error": "Invalid or expired access token."}, status=401)

    try:
        user = UserProfile.objects.select_related("tenant").get(id=token_data["user_id"])
    except UserProfile.DoesNotExist:
        return Response({"error": "User not found."}, status=401)

    tenant = user.tenant
    return Response({
        "sub": str(user.id),
        "email": user.email,
        "name": user.full_name,
        "picture": user.avatar_url,
        "tenant_id": str(tenant.tenant_id) if tenant else None,
        "tenant_name": tenant.name if tenant else None,
        "agent_access": user.get_accessible_agents(),
    })
