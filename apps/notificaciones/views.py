from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from .models import Notificacion


@method_decorator(login_required, name='dispatch')
class NotificacionesPageView(View):
    template_name = 'notificaciones/lista.html'

    def get(self, request):
        notificaciones = request.user.notificaciones.all()[:50]
        sin_leer = request.user.notificaciones.filter(leida=False).count()
        return render(request, self.template_name, {
            'notificaciones': notificaciones,
            'sin_leer': sin_leer,
        })


@method_decorator(login_required, name='dispatch')
class MarcarLeidaView(View):
    def post(self, request, pk):
        notif = get_object_or_404(Notificacion, pk=pk, usuario=request.user)
        notif.marcar_leida()
        return redirect('notificaciones-lista')


@method_decorator(login_required, name='dispatch')
class MarcarTodasLeidasView(View):
    def post(self, request):
        request.user.notificaciones.filter(leida=False).update(
            leida=True
        )
        return redirect('notificaciones-lista')


@method_decorator(login_required, name='dispatch')
class NotificacionesBadgeView(View):
    """AJAX endpoint: returns count of unread notifications."""
    def get(self, request):
        count = request.user.notificaciones.filter(leida=False).count()
        return JsonResponse({'sin_leer': count})
