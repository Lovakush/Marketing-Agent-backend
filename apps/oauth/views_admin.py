"""
Admin views for managing OAuth 2.0 clients.
All endpoints require IsSuperAdmin permission.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from apps.auth_app.permissions import IsSuperAdmin
from .models import OAuthClient
from .serializers import (
    OAuthClientSerializer,
    OAuthClientCreateSerializer,
    OAuthClientUpdateSerializer,
)


@api_view(["GET", "POST"])
@permission_classes([IsSuperAdmin])
def admin_clients_view(request):
    """
    GET  /oauth/admin/clients/  — List all registered OAuth clients
    POST /oauth/admin/clients/  — Register a new client (returns secret once)
    """
    if request.method == "GET":
        clients = OAuthClient.objects.all()
        return Response({
            "success": True,
            "data": OAuthClientSerializer(clients, many=True).data,
        })

    # POST — create new client
    serializer = OAuthClientCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    data = serializer.validated_data
    full_secret, secret_hash, secret_prefix = OAuthClient.generate_secret()

    client = OAuthClient.objects.create(
        name=data["name"],
        agent_type=data["agent_type"],
        redirect_uris=data["redirect_uris"],
        client_secret_hash=secret_hash,
        client_secret_prefix=secret_prefix,
    )

    return Response(
        {
            "success": True,
            "data": {
                **OAuthClientSerializer(client).data,
                "client_secret": full_secret,  # Shown ONCE — save immediately
            },
        },
        status=201,
    )


@api_view(["PATCH"])
@permission_classes([IsSuperAdmin])
def admin_client_detail_view(request, client_id):
    """
    PATCH /oauth/admin/clients/<uuid>/ — Update name, redirect_uris, or is_active
    """
    try:
        client = OAuthClient.objects.get(client_id=client_id)
    except OAuthClient.DoesNotExist:
        return Response({"success": False, "error": "Client not found."}, status=404)

    serializer = OAuthClientUpdateSerializer(client, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response({"success": False, "error": serializer.errors}, status=400)

    serializer.save()
    return Response({"success": True, "data": OAuthClientSerializer(client).data})


@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def admin_rotate_secret_view(request, client_id):
    """
    POST /oauth/admin/clients/<uuid>/rotate-secret/
    Generates a new client secret. The old secret is immediately invalidated.
    The new secret is returned once — save it immediately.
    """
    try:
        client = OAuthClient.objects.get(client_id=client_id)
    except OAuthClient.DoesNotExist:
        return Response({"success": False, "error": "Client not found."}, status=404)

    full_secret, secret_hash, secret_prefix = OAuthClient.generate_secret()
    client.client_secret_hash = secret_hash
    client.client_secret_prefix = secret_prefix
    client.save(update_fields=["client_secret_hash", "client_secret_prefix"])

    return Response({
        "success": True,
        "data": {
            "client_id": str(client.client_id),
            "client_secret": full_secret,  # Shown ONCE
            "client_secret_prefix": secret_prefix,
        },
    })
