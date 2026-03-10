from django.urls import path
from . import views, views_admin

urlpatterns = [
    # OAuth 2.0 / OIDC core endpoints
    path("authorize/", views.authorize_view, name="oauth-authorize"),
    path("token/", views.token_view, name="oauth-token"),
    path("userinfo/", views.userinfo_view, name="oauth-userinfo"),

    # Admin — manage OAuth clients (IsSuperAdmin)
    path("admin/clients/", views_admin.admin_clients_view, name="oauth-admin-clients"),
    path(
        "admin/clients/<uuid:client_id>/",
        views_admin.admin_client_detail_view,
        name="oauth-admin-client-detail",
    ),
    path(
        "admin/clients/<uuid:client_id>/rotate-secret/",
        views_admin.admin_rotate_secret_view,
        name="oauth-admin-rotate-secret",
    ),
]
