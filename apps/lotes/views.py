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
    if not user or not user.is_authenticated:
        return False
    return (
        getattr(user, 'rol', '') in ('admin', 'gerencia', 'superadmin')
        or getattr(user, 'is_staff', False)
        or getattr(user, 'is_superuser', False)
        or (hasattr(user, 'es_admin') and user.es_admin())
    )


@method_decorator(login_required, name='dispatch')
class RecoleccionPageView(View):
    def get(self, request):
        empresa_id = request.GET.get('empresa', '')
        solicitud_id = request.GET.get('solicitud', '')
        query = []
        if empresa_id:
            query.append(f"empresa={empresa_id}")
        if solicitud_id:
            query.append(f"solicitud={solicitud_id}")
        qs = f"?{'&'.join(query)}" if query else ""
        return redirect(f"/retiros/nuevo/{qs}")

    def post(self, request):
        return redirect('retiro-crear')


@method_decorator(login_required, name='dispatch')
class LoteDetallePageView(View):
    template_name = 'lotes/detalle.html'

    def get(self, request, codigo_lote):
        lote = get_object_or_404(Lote, codigo_lote=codigo_lote)
        eventos = lote.eventos.order_by('timestamp')
        return render(request, self.template_name, {'lote': lote, 'eventos': eventos})


@method_decorator(login_required, name='dispatch')
class LoteListView(View):
    def get(self, request):
        return redirect('retiros-lista')


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


@method_decorator(login_required, name='dispatch')
class LoteEditarView(View):
    template_name = 'lotes/editar.html'

    def get(self, request, codigo_lote):
        lote = get_object_or_404(Lote, codigo_lote=codigo_lote)
        if not (_es_admin(request.user) or lote.operador == request.user):
            messages.error(request, 'No tienes permiso para editar este lote.')
            return redirect('lote-detalle', codigo_lote=lote.codigo_lote)

        empresas = Empresa.objects.filter(estado='aprobada', activa=True) if _es_admin(request.user) else []
        return render(request, self.template_name, {
            'lote': lote,
            'empresas': empresas,
            'tipos_residuo': Lote.TIPOS_RESIDUO,
            'es_admin': _es_admin(request.user),
        })

    def post(self, request, codigo_lote):
        lote = get_object_or_404(Lote, codigo_lote=codigo_lote)
        if not (_es_admin(request.user) or lote.operador == request.user):
            messages.error(request, 'Sin permisos para modificar este lote.')
            return redirect('lote-detalle', codigo_lote=lote.codigo_lote)

        empresa_id = request.POST.get('empresa_origen')
        tipo_residuo = request.POST.get('tipo_residuo') or 'mixto'
        cantidad_kg_raw = request.POST.get('cantidad_kg') or '0'
        peso_final_raw = request.POST.get('peso_final_procesado')
        observaciones = request.POST.get('observaciones_recoleccion', '').strip()

        foto_ticket = request.FILES.get('foto_ticket')
        foto_recoleccion = request.FILES.get('foto_recoleccion')
        foto_camion = request.FILES.get('foto_camion')

        from decimal import Decimal
        try:
            # Guardar el mes original ANTES de modificar, para saber si cambió de período
            mes_original = lote.fecha_recoleccion.date().replace(day=1) if lote.fecha_recoleccion else None

            if _es_admin(request.user) and empresa_id:
                try:
                    lote.empresa_origen = Empresa.objects.get(id=empresa_id)
                except Empresa.DoesNotExist:
                    pass

            lote.tipo_residuo = tipo_residuo
            try:
                lote.cantidad_kg = Decimal(str(cantidad_kg_raw))
            except Exception:
                pass

            if peso_final_raw is not None and peso_final_raw != '':
                try:
                    lote.peso_final_procesado = Decimal(str(peso_final_raw))
                except Exception:
                    pass

            lote.observaciones_recoleccion = observaciones

            fecha_rec_raw = request.POST.get('fecha_recoleccion')
            if fecha_rec_raw:
                try:
                    from datetime import datetime
                    from django.utils import timezone
                    if 'T' in fecha_rec_raw:
                        dt = datetime.strptime(fecha_rec_raw, '%Y-%m-%dT%H:%M')
                    else:
                        dt = datetime.strptime(fecha_rec_raw, '%Y-%m-%d')
                    lote.fecha_recoleccion = timezone.make_aware(dt)
                except Exception:
                    pass

            if request.POST.get('eliminar_foto_ticket') == '1':
                lote.foto_ticket = None
            elif foto_ticket:
                lote.foto_ticket = foto_ticket

            if request.POST.get('eliminar_foto_recoleccion') == '1':
                lote.foto_recoleccion = None
            elif foto_recoleccion:
                lote.foto_recoleccion = foto_recoleccion

            if request.POST.get('eliminar_foto_camion') == '1':
                lote.foto_camion = None
            elif foto_camion:
                lote.foto_camion = foto_camion

            eliminar_extra_ids = request.POST.getlist('eliminar_extra_ids')
            if eliminar_extra_ids:
                from .models import EvidenciaLote
                EvidenciaLote.objects.filter(pk__in=eliminar_extra_ids, lote=lote).delete()

            lote.save()

            # Actualizar detalles de residuos si fueron enviados
            residuos_tipo = request.POST.getlist('residuos_tipo[]')
            residuos_cantidad = request.POST.getlist('residuos_cantidad[]')
            residuos_unidad = request.POST.getlist('residuos_unidad[]')

            if residuos_tipo and residuos_cantidad:
                from .models import DetalleLoteResiduo
                lote.detalles_residuos.all().delete()
                sum_kg = Decimal('0')
                for t, c, u in zip(residuos_tipo, residuos_cantidad, residuos_unidad):
                    if t and c:
                        try:
                            cant_val = Decimal(str(c))
                        except Exception:
                            cant_val = Decimal('0')
                        unid_val = u if u else 'kg'
                        DetalleLoteResiduo.objects.create(
                            lote=lote,
                            tipo_residuo=t,
                            cantidad=cant_val,
                            unidad=unid_val
                        )
                        if unid_val == 'kg':
                            sum_kg += cant_val
                if sum_kg > Decimal('0') and lote.cantidad_kg == Decimal('0'):
                    lote.cantidad_kg = sum_kg
                    lote.save()

            # Recalcular EDP de la empresa para el mes actual del lote
            try:
                from apps.empresas.models import actualizar_o_crear_edp_empresa
                mes_nuevo = lote.fecha_recoleccion.date().replace(day=1) if lote.fecha_recoleccion else None
                actualizar_o_crear_edp_empresa(lote.empresa_origen, usuario=request.user)

                # Si el mes cambió, también recalcular el EDP del mes anterior para eliminarlo de ahí
                if mes_original and mes_nuevo and mes_original != mes_nuevo:
                    import calendar
                    _, last_day = calendar.monthrange(mes_original.year, mes_original.month)
                    actualizar_o_crear_edp_empresa(
                        lote.empresa_origen,
                        periodo_inicio=mes_original,
                        periodo_fin=mes_original.replace(day=last_day),
                        usuario=request.user
                    )
            except Exception:
                pass

            messages.success(request, f'✅ Lote {lote.codigo_lote} modificado exitosamente.')
            return redirect('lote-detalle', codigo_lote=lote.codigo_lote)

        except Exception as e:
            messages.error(request, f'Error al modificar el lote: {e}')
            return redirect('lote-editar', codigo_lote=codigo_lote)

