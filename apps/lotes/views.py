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
        tipo_residuo = request.POST.get('tipo_residuo') or 'mixto'
        cantidad_kg_raw = request.POST.get('cantidad_kg') or '0'
        observaciones = request.POST.get('observaciones_recoleccion', '')
        ubicacion = request.POST.get('ubicacion_gps', '')
        solicitud_id = request.POST.get('solicitud_id')

        # Fotos por categoría
        foto_ticket = request.FILES.get('foto_ticket')
        fotos_residuos = request.FILES.getlist('foto_recoleccion')
        foto_camion = request.FILES.get('foto_camion')

        # Detalle de múltiples residuos
        residuos_tipo = request.POST.getlist('residuos_tipo[]')
        residuos_cantidad = request.POST.getlist('residuos_cantidad[]')
        residuos_unidad = request.POST.getlist('residuos_unidad[]')

        errores = []
        if not empresa_id:
            errores.append('Selecciona una empresa.')

        # Debe subir al menos 1 foto en cualquiera de los 3 apartados
        if not (foto_ticket or fotos_residuos or foto_camion):
            errores.append('Debes subir al menos una foto de evidencia (Ticket, Residuos o Camión).')

        if errores:
            empresas = Empresa.objects.filter(estado='aprobada', activa=True)
            return render(request, self.template_name, {
                'empresas': empresas, 'errores': errores, 'form_data': request.POST,
            })

        try:
            from decimal import Decimal
            empresa = Empresa.objects.get(id=empresa_id)
            foto_principal = fotos_residuos[0] if fotos_residuos else (foto_ticket or foto_camion)
            
            total_kg = Decimal('0')
            try:
                total_kg = Decimal(str(cantidad_kg_raw))
            except Exception:
                total_kg = Decimal('0')

            lote = Lote.objects.create(
                empresa_origen=empresa,
                operador=request.user,
                tipo_residuo=tipo_residuo,
                cantidad_kg=total_kg,
                foto_recoleccion=foto_principal,
                foto_ticket=foto_ticket,
                foto_camion=foto_camion,
                observaciones_recoleccion=observaciones,
                ubicacion_gps=ubicacion,
            )

            # Guardar múltiples detalles de residuos si fueron especificados
            from .models import DetalleLoteResiduo, EvidenciaLote
            if residuos_tipo and residuos_cantidad:
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
                if sum_kg > Decimal('0') and total_kg == Decimal('0'):
                    lote.cantidad_kg = sum_kg
                    lote.save()
            
            # Guardamos fotos de residuos adicionales como evidencia extra
            if fotos_residuos:
                for i, f in enumerate(fotos_residuos):
                    if i > 0:
                        EvidenciaLote.objects.create(lote=lote, foto=f)

            # Si viene gestionada de una Solicitud, marcarla completada
            if solicitud_id:
                from apps.empresas.models import SolicitudRecoleccion
                try:
                    s = SolicitudRecoleccion.objects.get(pk=solicitud_id)
                    s.estado = 'completada'
                    s.save()
                except Exception:
                    pass

            # Auto-generar/actualizar Estado de Pago (EDP) cobrando por SERVICIO
            try:
                from apps.empresas.models import actualizar_o_crear_edp_empresa
                actualizar_o_crear_edp_empresa(empresa, usuario=request.user)
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
                        f'{request.user.nombre_completo} registró retiro de '
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

            # Recalcular EDP de la empresa
            try:
                from apps.empresas.models import actualizar_o_crear_edp_empresa
                actualizar_o_crear_edp_empresa(lote.empresa_origen, usuario=request.user)
            except Exception:
                pass

            messages.success(request, f'✅ Lote {lote.codigo_lote} modificado exitosamente.')
            return redirect('lote-detalle', codigo_lote=lote.codigo_lote)

        except Exception as e:
            messages.error(request, f'Error al modificar el lote: {e}')
            return redirect('lote-editar', codigo_lote=codigo_lote)

