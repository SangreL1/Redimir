from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', RedirectView.as_view(url='/login/', permanent=False)),
    path('admin/', admin.site.urls),
    path('', include('apps.usuarios.urls')),
    path('', include('apps.empresas.urls')),
    path('', include('apps.lotes.urls')),
    path('', include('apps.dashboard.urls')),
    path('', include('apps.certificados.urls')),
    path('', include('apps.notificaciones.urls')),
    path('', include('apps.servicios.urls')),
    path('', include('apps.calculadora.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

