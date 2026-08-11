from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from apps.empresas.models import Empresa
from apps.eventos.models import Evento
from apps.notificaciones.models import Notificacion
from apps.usuarios.models import Usuario
from .models import Lote


def _es_admin(user):
    return user.rol == 'admin' or user.is_staff


@method_decorator(login_required, name='dispatch')
class RecoleccionPageView(View):
    template_name = 'recolecciones/formulario.html'

    def get(self, request):
        if _es_admin(request.user):
            empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        elif request.user.empresa and request.user.empresa.estado == 'aprobada':
            empresas = Empresa.objects.filter(pk=request.user.empresa.pk)
        else:
            empresas = Empresa.objects.filter(estado='aprobada', activa=True)
            
        form_data = {}
        empresa_id = request.GET.get('empresa')
        if empresa_id:
            form_data['empresa_origen'] = empresa_id
            
        solicitud_id = request.GET.get('solicitud')
        if solicitud_id:
            from apps.empresas.models import SolicitudRecoleccion
            try:
                s = SolicitudRecoleccion.objects.get(pk=solicitud_id)
                desc = s.descripcion.lower()
                # Guess tipo from description tag like [PLASTICO]
                for tipo in ['plastico', 'metal', 'papel', 'vidrio', 'organico', 'mixto']:
                    if tipo in desc:
                        form_data['tipo_residuo'] = tipo
                        break
                form_data['observaciones_recoleccion'] = s.observaciones
                form_data['solicitud_id'] = s.id
            except Exception:
                pass

        return render(request, self.template_name, {
            'empresas': empresas,
            'form_data': form_data
        })

    def post(self, request):
        empresa_id = request.POST.get('empresa_origen')
        tipo_residuo = request.POST.get('tipo_residuo')
        cantidad_kg = request.POST.get('cantidad_kg')
        observaciones = request.POST.get('observaciones_recoleccion', '')
        fotos = request.FILES.getlist('foto_recoleccion')
        ubicacion = request.POST.get('ubicacion_gps', '')
        solicitud_id = request.POST.get('solicitud_id')

        errores = []
        if not empresa_id:
            errores.append('Selecciona una empresa.')
        if not tipo_residuo:
            errores.append('Selecciona el tipo de residuo.')
        if not cantidad_kg:
            errores.append('Ingresa la cantidad en kg.')
        if not fotos:
            errores.append('Debes subir al menos una foto de evidencia.')

        if errores:
            empresas = Empresa.objects.filter(estado='aprobada', activa=True)
            return render(request, self.template_name, {
                'empresas': empresas, 'errores': errores, 'form_data': request.POST,
            })

        try:
            empresa = Empresa.objects.get(id=empresa_id)
            foto_principal = fotos[0] if fotos else None
            
            lote = Lote.objects.create(
                empresa_origen=empresa,
                operador=request.user,
                tipo_residuo=tipo_residuo,
                cantidad_kg=cantidad_kg,
                foto_recoleccion=foto_principal,
                observaciones_recoleccion=observaciones,
                ubicacion_gps=ubicacion,
            )
            
            # Guardamos las demas fotos (o todas) como evidencia
            from .models import EvidenciaLote
            for i, f in enumerate(fotos):
                if i > 0: # La primera ya está como foto_recoleccion del Lote
                    EvidenciaLote.objects.create(lote=lote, foto=f)

            # Si viene gestionada de una Solicitud, marcarla completada!
            if solicitud_id:
                from apps.empresas.models import SolicitudRecoleccion
                try:
                    s = SolicitudRecoleccion.objects.get(pk=solicitud_id)
                    s.estado = 'completada'
                    s.save()
                except Exception:
                    pass

            # Notify all admins about new collection
            admins = Usuario.objects.filter(rol='admin', is_active=True, estado='aprobado')
            notifs = [
                Notificacion(
                    usuario=admin,
                    tipo='recoleccion_confirmada',
                    titulo='Nueva Recolección Registrada',
                    mensaje=(
                        f'{request.user.nombre_completo} registró {cantidad_kg} kg de '
                        f'{lote.get_tipo_residuo_display()} en {empresa.nombre}'
                    ),
                    url_destino=f'/lotes/{lote.codigo_lote}/',
                )
                for admin in admins
            ]
            Notificacion.objects.bulk_create(notifs)

            messages.success(request, f'Recolección {lote.codigo_lote} registrada exitosamente.')
            return redirect('lote-detalle', codigo_lote=lote.codigo_lote)
        except Exception as e:
            empresas = Empresa.objects.filter(estado='aprobada', activa=True)
            return render(request, self.template_name, {
                'empresas': empresas, 'errores': [str(e)], 'form_data': request.POST,
            })


@method_decorator(login_required, name='dispatch')
class LoteDetallePageView(View):
    template_name = 'lotes/detalle.html'

    def get(self, request, codigo_lote):
        lote = get_object_or_404(Lote, codigo_lote=codigo_lote)
        eventos = lote.eventos.order_by('timestamp')
        return render(request, self.template_name, {'lote': lote, 'eventos': eventos})


@method_decorator(login_required, name='dispatch')
class LoteListView(View):
    template_name = 'lotes/lista.html'

    def get(self, request):
        if _es_admin(request.user):
            lotes = Lote.objects.all().select_related('empresa_origen', 'operador').order_by('-fecha_creacion')
        else:
            lotes = Lote.objects.filter(operador=request.user).select_related('empresa_origen').order_by('-fecha_creacion')
        return render(request, self.template_name, {'lotes': lotes})


@method_decorator(login_required, name='dispatch')
class LoteProcesarPageView(View):
    template_name = 'lotes/procesar.html'

    def get(self, request, codigo_lote):
        lote = get_object_or_404(Lote, codigo_lote=codigo_lote)
        return render(request, self.template_name, {'lote': lote})

    def post(self, request, codigo_lote):
        lote = get_object_or_404(Lote, codigo_lote=codigo_lote)
        peso_final = request.POST.get('peso_final_procesado')
        foto = request.FILES.get('foto_procesamiento')

        if not peso_final:
            messages.error(request, 'El peso final es requerido.')
            return render(request, self.template_name, {'lote': lote})

        lote.peso_final_procesado = peso_final
        if foto:
            lote.foto_procesamiento = foto
        lote.estado = 'procesado'
        lote.usuario_procesamiento = request.user
        lote.save()

        messages.success(request, f'Lote {lote.codigo_lote} procesado correctamente.')
        return redirect('lote-detalle', codigo_lote=lote.codigo_lote)
