from django.urls import path
from core import views

urlpatterns = [
    path("api/health/", views.health),
    path("api/bootstrap/", views.bootstrap),
    path("api/login/", views.login),
    path("api/people/", views.people),
    path("api/people/<int:person_id>/status/", views.person_status),
    path("api/alerts/<int:alert_id>/resolve/", views.resolve_alert),
    path("api/access/", views.access_register),
]
