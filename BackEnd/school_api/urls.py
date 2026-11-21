from django.urls import path

from core import views

urlpatterns = [
    path("api/health/", views.health),
    path("api/login/", views.login),
    path("api/logout/", views.logout),
    path("api/me/", views.me),
    path("api/bootstrap/", views.bootstrap),
    path("api/dashboard/", views.dashboard),
    path("api/live/", views.live_updates),
    path("api/logs/", views.logs_list),
    path("api/alerts/", views.alerts_list),
    path("api/classes/", views.classes),
    path("api/people/", views.people),
    path("api/people/<str:person_ref>/", views.person),
    path("api/people/<str:person_ref>/status/", views.person_status),
    path("api/people/<str:person_ref>/biometrics/", views.person_biometrics),
    path("api/people/<str:person_ref>/face/", views.person_biometrics),
    path("api/alerts/<int:alert_id>/", views.update_alert),
    path("api/alerts/<int:alert_id>/resolve/", views.update_alert),
    path("api/settings/", views.school_settings),
    path("api/devices/", views.devices),
    path("api/devices/<int:device_id>/", views.device_detail),
    path("api/audit/", views.audit_logs),
    path("api/reports/export/", views.reports_export),
    path("api/access/", views.access_register),
    # Endpoints dos terminais autônomos da portaria
    path("api/portaria/config/", views.portaria_config),
    path("api/portaria/biometrics/", views.portaria_biometrics),
    path("api/portaria/events/", views.portaria_events),
    path("api/portaria/heartbeat/", views.portaria_heartbeat),
]
