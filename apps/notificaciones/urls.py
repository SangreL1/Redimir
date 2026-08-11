from django.urls import path
from .views import NotificacionesPageView, MarcarLeidaView, MarcarTodasLeidasView, NotificacionesBadgeView

urlpatterns = [
    path('notificaciones/', NotificacionesPageView.as_view(), name='notificaciones-lista'),
    path('notificaciones/<int:pk>/leer/', MarcarLeidaView.as_view(), name='notificacion-leer'),
    path('notificaciones/leer-todas/', MarcarTodasLeidasView.as_view(), name='notificaciones-leer-todas'),
    path('api/notificaciones/badge/', NotificacionesBadgeView.as_view(), name='notificaciones-badge'),
]
