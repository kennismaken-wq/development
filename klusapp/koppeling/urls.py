from django.urls import path

from . import mcp, oauth, views

urlpatterns = [
    # Claude plakt het adres soms met en soms zonder slash; allebei goed.
    path("mcp", mcp.eindpunt, name="mcp"),
    path("mcp/", mcp.eindpunt),
    path(".well-known/oauth-protected-resource", oauth.protected_resource),
    path(".well-known/oauth-protected-resource/mcp", oauth.protected_resource),
    path(".well-known/oauth-authorization-server", oauth.authorization_server),
    path("oauth/registreren/", oauth.registreren, name="oauth_registreren"),
    path("oauth/toestaan/", oauth.toestaan, name="oauth_toestaan"),
    path("oauth/token/", oauth.token, name="oauth_token"),
    path("claude/", views.koppelingen, name="claude_koppeling"),
    path("claude/<int:pk>/intrekken/", views.intrekken, name="claude_intrekken"),
]
