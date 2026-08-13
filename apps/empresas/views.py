from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import timedelta

from apps.usuarios.models import Usuario
from apps.notificaciones.models import Notificacion
from apps.lotes.models import Lote
from .models import Empresa, SolicitudRecoleccion


def _es_admin(user):
    return user.rol == 'admin' or user.is_staff


# ─── Lista y Gestión de Empresas (admin Redimir) ──────────────────────────────

@method_decorator(login_required, name='dispatch')
class EmpresaListView(View):
    template_name = 'empresas/lista.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')
        empresas = Empresa.objects.all().order_by('-fecha_registro')
        return render(request, self.template_name, {'empresas': empresas})


@method_decorator(login_required, name='dispatch')
class EmpresaDeleteView(View):
    def post(self, request, pk):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')
        empresa = get_object_or_404(Empresa, pk=pk)
        if empresa.lotes.exists():
            messages.error(
                request,
                f'No se puede eliminar "{empresa.nombre}" porque tiene {empresa.lotes.count()} recolecciones asociadas.'
            )
        else:
            nombre = empresa.nombre
            usuarios_asociados = Usuario.objects.filter(empresa=empresa)
            cant_usuarios = usuarios_asociados.count()
            
            # Registrar en auditoría de seguridad
            from apps.usuarios.models import AuditLog
            AuditLog.registrar(
                usuario=request.user,
                accion='eliminacion',
                modelo='Empresa',
                registro_id=empresa.pk,
                detalles=f"Empresa '{nombre}' y {cant_usuarios} usuario(s) asociado(s) eliminados permanentemente del sistema.",
                ip=request.META.get('REMOTE_ADDR')
            )
            
            usuarios_asociados.delete()
            empresa.delete()
            messages.success(
                request, 
                f'Empresa "{nombre}" y sus {cant_usuarios} usuario(s) asociado(s) fueron eliminados permanentemente (acceso revocado).'
            )
        return redirect('empresa-list')


# ─── PORTAL DE EMPRESA ────────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class EmpresaPortalView(View):
    """Dashboard/KPI panel for empresa users."""
    template_name = 'empresa_portal/dashboard.html'

    def get(self, request):
        if not request.user.es_empresa():
            messages.error(request, 'Este panel es exclusivo para empresas.')
            return redirect('dashboard')

        empresa = request.user.empresa
        if not empresa:
            return render(request, 'empresa_portal/sin_empresa.html')

        if empresa.estado != 'aprobada':
            return render(request, 'empresa_portal/pendiente.html', {'empresa': empresa})

        hace_30 = timezone.now() - timedelta(days=30)
        lotes   = Lote.objects.filter(empresa_origen=empresa)
        lotes_mes = lotes.filter(fecha_creacion__gte=hace_30)

        kg_mes     = lotes_mes.aggregate(Sum('cantidad_kg'))['cantidad_kg__sum'] or 0
        rec_mes    = lotes_mes.count()
        kg_total   = lotes.aggregate(Sum('cantidad_kg'))['cantidad_kg__sum'] or 0
        sol_pend   = SolicitudRecoleccion.objects.filter(empresa=empresa, estado='pendiente').count()

        # Trend 7 días
        trend_labels, trend_values = [], []
        for i in range(6, -1, -1):
            dia = timezone.now().date() - timedelta(days=i)
            kg  = lotes.filter(fecha_creacion__date=dia).aggregate(Sum('cantidad_kg'))['cantidad_kg__sum'] or 0
            trend_labels.append(dia.strftime('%d/%m'))
            trend_values.append(float(kg))

        # Por tipo de residuo
        tipos_data = lotes_mes.values('tipo_residuo').annotate(total=Sum('cantidad_kg'))
        tipos_labels = [t['tipo_residuo'].capitalize() for t in tipos_data]
        tipos_values = [float(t['total']) for t in tipos_data]

        ultimas = lotes.order_by('-fecha_creacion')[:5].select_related('operador')
        ultimas_sols = SolicitudRecoleccion.objects.filter(empresa=empresa).order_by('-fecha_creacion')[:5]

        return render(request, self.template_name, {
            'empresa': empresa,
            'kg_mes': float(kg_mes),
            'rec_mes': rec_mes,
            'kg_total': float(kg_total),
            'sol_pend': sol_pend,
            'trend_labels': trend_labels,
            'trend_values': trend_values,
            'tipos_labels': tipos_labels,
            'tipos_values': tipos_values,
            'ultimas': ultimas,
            'ultimas_sols': ultimas_sols,
        })


@method_decorator(login_required, name='dispatch')
class EmpresaSolicitudCrearView(View):
    """Empresa user creates a recoleccion request."""
    template_name = 'empresa_portal/crear_solicitud.html'

    def get(self, request):
        if not request.user.es_empresa():
            return redirect('dashboard')
        empresa = request.user.empresa
        if not empresa or empresa.estado != 'aprobada':
            messages.error(request, 'Tu empresa no está habilitada.')
            return redirect('dashboard')
        return render(request, self.template_name, {'empresa': empresa})

    def post(self, request):
        if not request.user.es_empresa():
            return redirect('dashboard')

        empresa = request.user.empresa
        if not empresa or empresa.estado != 'aprobada':
            return redirect('dashboard')

        modulo         = request.POST.get('modulo', 'reciclables')
        tipo_material  = request.POST.get('tipo_material', 'carton')
        descripcion    = request.POST.get('descripcion', '').strip()
        direccion      = request.POST.get('direccion_recoleccion', '').strip()
        fecha_str      = request.POST.get('fecha_solicitada', '')
        cant_est_raw   = request.POST.get('cantidad_estimada', '0')
        unidad_med     = request.POST.get('unidad_medida', 'kg')
        precio_u_raw   = request.POST.get('precio_unitario', '0')
        total_est_raw  = request.POST.get('total_estimado', '0')
        observaciones  = request.POST.get('observaciones', '').strip()

        from decimal import Decimal
        try:
            cant_est  = Decimal(cant_est_raw) if cant_est_raw else Decimal('0')
            precio_u  = Decimal(precio_u_raw) if precio_u_raw else Decimal('0')
            total_est = Decimal(total_est_raw) if total_est_raw else Decimal('0')
        except Exception:
            cant_est = precio_u = total_est = Decimal('0')

        errores = []
        if not descripcion:
            errores.append('La descripción es obligatoria.')
        if not direccion:
            errores.append('La dirección es obligatoria.')
        if not fecha_str:
            errores.append('La fecha es obligatoria.')

        if errores:
            return render(request, self.template_name, {
                'empresa': empresa, 'errores': errores, 'form_data': request.POST,
            })

        from datetime import datetime
        try:
            fecha_solicitada = datetime.fromisoformat(fecha_str)
        except ValueError:
            fecha_solicitada = timezone.now()

        solicitud = SolicitudRecoleccion.objects.create(
            empresa=empresa,
            modulo=modulo,
            tipo_material=tipo_material,
            cantidad_estimada=cant_est,
            unidad_medida=unidad_med,
            precio_unitario=precio_u,
            total_estimado=total_est,
            descripcion=descripcion,
            direccion_recoleccion=direccion,
            fecha_solicitada=fecha_solicitada,
            observaciones=observaciones,
            creado_por=request.user,
        )

        # Auto-generar/actualizar Estado de Pago único de la empresa
        from .models import actualizar_o_crear_edp_empresa
        actualizar_o_crear_edp_empresa(empresa, usuario=request.user)

        # Notify all admins
        admins = Usuario.objects.filter(rol='admin', is_active=True, estado='aprobado')
        notifs = [
            Notificacion(
                usuario=adm,
                tipo='nueva_solicitud',
                titulo=f'Nueva Solicitud — {empresa.nombre}',
                mensaje=f'Solicita recolección de {tipo_material.upper()} en {direccion}',
                url_destino='/solicitudes/',
            )
            for adm in admins
        ]
        Notificacion.objects.bulk_create(notifs)

        # Notify all recolectors since any of them can accept it
        recolectores = Usuario.objects.filter(rol='recolector', estado='aprobado', is_active=True)
        notifs_rec = [
            Notificacion(
                usuario=r,
                tipo='nueva_solicitud',
                titulo='Nueva Solicitud Disponible',
                mensaje=f'{empresa.nombre} solicita recolección en {direccion}',
                url_destino='/solicitudes/',
            )
            for r in recolectores
        ]
        Notificacion.objects.bulk_create(notifs_rec)

        messages.success(request, f'Solicitud #{solicitud.pk} enviada y Estado de Pago actualizado automáticamente.')
        return redirect('empresa-solicitudes')


@method_decorator(login_required, name='dispatch')
class EmpresaSolicitudListView(View):
    """Empresa user views their own solicitudes + history."""
    template_name = 'empresa_portal/solicitudes.html'

    def get(self, request):
        if not request.user.es_empresa():
            return redirect('dashboard')
        empresa = request.user.empresa
        if not empresa:
            return redirect('dashboard')

        solicitudes = SolicitudRecoleccion.objects.filter(empresa=empresa).select_related('operador_asignado')
        return render(request, self.template_name, {
            'solicitudes': solicitudes,
            'empresa': empresa,
        })


@method_decorator(login_required, name='dispatch')
class EmpresaGuiaReciclajeView(View):
    """Guía interactiva ¿Cómo debo reciclar? para el portal de clientes empresa."""
    template_name = 'empresa_portal/guia_reciclaje.html'

    def get(self, request):
        if not request.user.es_empresa():
            messages.error(request, 'Esta guía es para el portal de empresas.')
            return redirect('dashboard')
        return render(request, self.template_name, {'empresa': getattr(request.user, 'empresa', None)})


# ─── Solicitudes de Recolección (admin + recolector) ─────────────────────────


@method_decorator(login_required, name='dispatch')
class SolicitudListView(View):
    template_name = 'empresas/solicitudes.html'

    def get(self, request):
        from django.db import models
        if _es_admin(request.user):
            solicitudes = SolicitudRecoleccion.objects.select_related('empresa', 'operador_asignado').all()
        elif request.user.es_recolector():
            solicitudes = SolicitudRecoleccion.objects.filter(
                models.Q(estado='pendiente') | models.Q(operador_asignado=request.user)
            ).select_related('empresa', 'operador_asignado')
        elif request.user.es_empresa():
            return redirect('empresa-solicitudes')
        else:
            solicitudes = SolicitudRecoleccion.objects.none()
            solicitudes = SolicitudRecoleccion.objects.none()
        return render(request, self.template_name, {'solicitudes': solicitudes})


@method_decorator(login_required, name='dispatch')
class SolicitudCrearView(View):
    template_name = 'empresas/crear_solicitud.html'

    def get(self, request):
        if not _es_admin(request.user):
            return redirect('dashboard')
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        return render(request, self.template_name, {'empresas': empresas})

    def post(self, request):
        if not _es_admin(request.user):
            return redirect('dashboard')

        empresa_id    = request.POST.get('empresa')
        modulo        = request.POST.get('modulo', 'reciclables')
        tipo_material = request.POST.get('tipo_material', 'carton')
        cant_est_raw  = request.POST.get('cantidad_estimada', '0')
        unidad_med    = request.POST.get('unidad_medida', 'kg')
        precio_u_raw  = request.POST.get('precio_unitario', '0')
        total_est_raw = request.POST.get('total_estimado', '0')
        descripcion   = request.POST.get('descripcion', '').strip()
        direccion     = request.POST.get('direccion_recoleccion', '').strip()
        fecha_str     = request.POST.get('fecha_solicitada', '')
        observaciones = request.POST.get('observaciones', '').strip()

        from decimal import Decimal
        try:
            cant_est  = Decimal(cant_est_raw) if cant_est_raw else Decimal('0')
            precio_u  = Decimal(precio_u_raw) if precio_u_raw else Decimal('0')
            total_est = Decimal(total_est_raw) if total_est_raw else Decimal('0')
        except Exception:
            cant_est = precio_u = total_est = Decimal('0')

        errores = []
        if not empresa_id:   errores.append('Selecciona una empresa.')
        if not descripcion:  errores.append('La descripción es obligatoria.')
        if not direccion:    errores.append('La dirección es obligatoria.')
        if not fecha_str:    errores.append('La fecha es obligatoria.')

        empresa = None
        if empresa_id:
            try:
                empresa = Empresa.objects.get(pk=empresa_id, estado='aprobada')
            except Empresa.DoesNotExist:
                errores.append('Empresa no válida.')

        if errores:
            empresas = Empresa.objects.filter(estado='aprobada', activa=True)
            return render(request, self.template_name, {
                'errores': errores, 'form_data': request.POST, 'empresas': empresas,
            })

        from datetime import datetime
        try:
            fecha_solicitada = datetime.fromisoformat(fecha_str)
        except ValueError:
            fecha_solicitada = timezone.now()

        solicitud = SolicitudRecoleccion.objects.create(
            empresa=empresa,
            modulo=modulo,
            tipo_material=tipo_material,
            cantidad_estimada=cant_est,
            unidad_medida=unidad_med,
            precio_unitario=precio_u,
            total_estimado=total_est,
            descripcion=descripcion,
            direccion_recoleccion=direccion,
            fecha_solicitada=fecha_solicitada,
            observaciones=observaciones,
            creado_por=request.user,
        )

        # Auto-generar/actualizar Estado de Pago único de la empresa
        from .models import actualizar_o_crear_edp_empresa
        actualizar_o_crear_edp_empresa(empresa, usuario=request.user)

        recolectores = Usuario.objects.filter(empresa=empresa, rol='recolector', estado='aprobado', is_active=True)
        notifs = [
            Notificacion(
                usuario=r, tipo='nueva_solicitud',
                titulo='Nueva Solicitud de Recolección',
                mensaje=f'{empresa.nombre} solicita recolección en {direccion}',
                url_destino='/solicitudes/',
            )
            for r in recolectores
        ]
        Notificacion.objects.bulk_create(notifs)
        messages.success(request, f'Solicitud #{solicitud.pk} creada y Estado de Pago actualizado automáticamente.')
        return redirect('solicitud-lista')


@method_decorator(login_required, name='dispatch')
class SolicitudAceptarView(View):
    def post(self, request, pk):
        if not request.user.es_recolector():
            messages.error(request, 'Solo recolectores pueden aceptar solicitudes.')
            return redirect('dashboard')
        solicitud = get_object_or_404(SolicitudRecoleccion, pk=pk, estado='pendiente')
        solicitud.operador_asignado = request.user
        solicitud.estado = 'asignada'
        solicitud.save()
        if solicitud.creado_por:
            Notificacion.objects.create(
                usuario=solicitud.creado_por,
                tipo='solicitud_asignada',
                titulo='Solicitud Asignada',
                mensaje=f'{request.user.nombre_completo} aceptó la solicitud #{solicitud.pk}',
                url_destino='/solicitudes/',
            )
        messages.success(request, f'Solicitud #{solicitud.pk} aceptada.')
        return redirect('dashboard-recolector')


@method_decorator(login_required, name='dispatch')
class SolicitudCompletarView(View):
    def post(self, request, pk):
        if _es_admin(request.user):
            solicitud = get_object_or_404(SolicitudRecoleccion, pk=pk)
        else:
            solicitud = get_object_or_404(SolicitudRecoleccion, pk=pk, operador_asignado=request.user)
        solicitud.estado = 'completada'
        solicitud.fecha_completada = timezone.now()
        solicitud.save()
        # notify the empresa contact
        contacto = Usuario.objects.filter(empresa=solicitud.empresa, rol='empresa').first()
        if contacto:
            Notificacion.objects.create(
                usuario=contacto,
                tipo='recoleccion_confirmada',
                titulo='Solicitud Completada',
                mensaje=f'Tu solicitud #{solicitud.pk} fue completada exitosamente.',
                url_destino='/empresa/solicitudes/',
            )
        messages.success(request, f'Solicitud #{solicitud.pk} completada.')
        return redirect('solicitud-lista')


@method_decorator(login_required, name='dispatch')
class SolicitudCancelarView(View):
    def post(self, request, pk):
        if not _es_admin(request.user):
            messages.error(request, 'Solo administradores pueden cancelar solicitudes.')
            return redirect('solicitud-lista')
        solicitud = get_object_or_404(SolicitudRecoleccion, pk=pk)
        solicitud.estado = 'cancelada'
        solicitud.save()
        messages.success(request, f'Solicitud #{solicitud.pk} cancelada.')
        return redirect('solicitud-lista')


# ─── ESTADOS DE PAGO INTERNOS (Punto 16) ──────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class EstadoDePagoListView(View):
    template_name = 'empresas/estados_de_pago.html'

    def get(self, request):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso restringido únicamente a Gerencia y Administradores.')
            return redirect('dashboard')
        
        from .models import EstadoDePago
        edps = EstadoDePago.objects.all().select_related('empresa')
        return render(request, self.template_name, {'edps': edps})


@method_decorator(login_required, name='dispatch')
class EstadoDePagoCrearView(View):
    template_name = 'empresas/crear_edp.html'

    def get(self, request):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso restringido.')
            return redirect('dashboard')
        
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        return render(request, self.template_name, {'empresas': empresas})

    def post(self, request):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            return redirect('dashboard')

        empresa_id = request.POST.get('empresa_id')
        inicio     = request.POST.get('inicio')
        fin        = request.POST.get('fin')
        subtotal_raw = request.POST.get('subtotal_neto', '0')
        estado_val   = request.POST.get('estado', 'borrador')
        obs        = request.POST.get('observaciones', '').strip()

        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        errores = []

        if not empresa_id or not inicio or not fin:
            errores.append('Empresa y período son obligatorios.')

        try:
            from decimal import Decimal
            subtotal = Decimal(subtotal_raw)
        except Exception:
            subtotal = Decimal('0')
            errores.append('El monto subtotal ingresado no es válido.')

        if errores:
            return render(request, self.template_name, {'empresas': empresas, 'errores': errores})

        try:
            from django.db.models import Q
            from .models import EstadoDePago, DetalleEstadoDePago, TarifaEmpresa
            from apps.servicios.models import Servicio
            
            empresa = Empresa.objects.get(pk=empresa_id)
            
            # Búsqueda flexible de retiros validados o completados dentro del rango
            servicios_qs = Servicio.objects.filter(
                empresa=empresa,
                estado__in=['validado', 'documento_emitido', 'cerrado', 'retirado', 'pendiente_validacion']
            ).filter(
                Q(fecha_retiro_real__date__range=[inicio, fin]) |
                Q(fecha_programada__date__range=[inicio, fin]) |
                Q(fecha_solicitud__date__range=[inicio, fin])
            ).distinct()

            servicios_count = servicios_qs.count()

            edp = EstadoDePago.objects.create(
                empresa=empresa,
                periodo_inicio=inicio,
                periodo_fin=fin,
                total_servicios=servicios_count,
                subtotal_neto=Decimal('0'),
                iva=Decimal('0'),
                total_bruto=Decimal('0'),
                estado=estado_val,
                observaciones=obs,
                creado_por=request.user
            )

            total_calculado = Decimal('0')

            for s in servicios_qs:
                reg = s.get_registro()
                cant = Decimal('1')
                unid = 'servicio'
                desc = f"Retiro {s.get_modulo_display()} — Solicitud #{s.id}"
                mat_key = s.modulo

                # Tarifas por defecto si no hay tarifa personalizada
                tarifa = Decimal('15000')
                if s.modulo == 'rsd': tarifa = Decimal('120')
                elif s.modulo == 'escombros': tarifa = Decimal('18000')
                elif s.modulo == 'reciclables': tarifa = Decimal('150')

                if reg:
                    if s.modulo == 'rsd':
                        if hasattr(reg, 'cantidad_kg') and reg.cantidad_kg > 0:
                            cant = Decimal(str(reg.cantidad_kg))
                            unid = 'kg'
                    elif s.modulo == 'escombros':
                        if hasattr(reg, 'cantidad') and reg.cantidad > 0:
                            cant = Decimal(str(reg.cantidad))
                            unid = reg.get_unidad_display() if hasattr(reg, 'get_unidad_display') else 'm3'
                    elif s.modulo == 'reciclables':
                        if hasattr(reg, 'cantidad_kg') and reg.cantidad_kg > 0:
                            cant = Decimal(str(reg.cantidad_kg))
                            unid = 'kg'
                        if hasattr(reg, 'tipo_material') and reg.tipo_material:
                            mat_key = str(reg.tipo_material).lower()
                            desc = f"Reciclaje ({mat_key.upper()}) — Solicitud #{s.id}"

                # Buscar si existe tarifa personalizada configurada para la empresa
                tarifa_custom = TarifaEmpresa.objects.filter(
                    empresa=empresa,
                    modulo=s.modulo,
                    tipo_material__iexact=mat_key
                ).first()

                if not tarifa_custom:
                    tarifa_custom = TarifaEmpresa.objects.filter(
                        empresa=empresa,
                        modulo=s.modulo
                    ).first()

                if tarifa_custom:
                    tarifa = tarifa_custom.precio_unitario
                    if tarifa_custom.unidad_medida:
                        unid = tarifa_custom.unidad_medida

                sub_item = cant * tarifa
                total_calculado += sub_item

                DetalleEstadoDePago.objects.create(
                    estado_de_pago=edp,
                    servicio=s,
                    fecha_servicio=s.fecha_retiro_real.date() if s.fecha_retiro_real else (s.fecha_solicitud.date() if s.fecha_solicitud else None),
                    modulo=s.get_modulo_display(),
                    descripcion=desc,
                    cantidad=cant,
                    unidad_medida=unid,
                    tarifa_unitaria=tarifa,
                    subtotal=sub_item
                )

            # Si se ingresó subtotal manual diferente de 0, prevalece el ingresado
            if subtotal > 0:
                edp.subtotal_neto = subtotal
            else:
                edp.subtotal_neto = total_calculado

            edp.iva = round(edp.subtotal_neto * Decimal('0.19'), 2)
            edp.total_bruto = edp.subtotal_neto + edp.iva
            edp.save()

            # Auditoría estructurada (Fase 2 y 11)
            from apps.usuarios.models import AuditLog
            AuditLog.registrar(
                usuario=request.user,
                accion='creacion',
                modelo='EstadoDePago',
                registro_id=edp.numero_edp,
                campo='total_bruto',
                valor_anterior='0',
                valor_nuevo=str(edp.total_bruto),
                detalles=f"Generado EDP {edp.numero_edp} para {empresa.nombre} con {edp.detalles.count()} ítems desglosados.",
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f"Estado de Pago {edp.numero_edp} generado exitosamente con {edp.detalles.count()} ítems desglosados.")
            return redirect('estados-de-pago-lista')

        except Exception as e:
            return render(request, self.template_name, {'empresas': empresas, 'errores': [str(e)]})


@method_decorator(login_required, name='dispatch')
class EstadoDePagoDetalleView(View):
    """Ver el desglose comercial impreso de un Estado de Pago."""
    def get(self, request, pk):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso restringido.')
            return redirect('dashboard')

        from .models import EstadoDePago
        edp = get_object_or_404(EstadoDePago, pk=pk)
        return render(request, 'empresas/detalle_edp.html', {'edp': edp})


@method_decorator(login_required, name='dispatch')
class EstadoDePagoEditarView(View):
    """Editar estado, observaciones o montos de un Estado de Pago."""
    def post(self, request, pk):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso denegado.')
            return redirect('dashboard')

        from .models import EstadoDePago
        edp = get_object_or_404(EstadoDePago, pk=pk)
        nuevo_estado = request.POST.get('estado', edp.estado)
        obs = request.POST.get('observaciones', edp.observaciones)

        estado_anterior = edp.get_estado_display()
        edp.estado = nuevo_estado
        edp.observaciones = obs
        edp.save()

        from apps.usuarios.models import AuditLog
        AuditLog.registrar(
            usuario=request.user,
            accion='modificacion',
            modelo='EstadoDePago',
            registro_id=edp.numero_edp,
            campo='estado',
            valor_anterior=estado_anterior,
            valor_nuevo=edp.get_estado_display(),
            detalles=f"Estado de Pago {edp.numero_edp} actualizado a estado '{edp.get_estado_display()}'.",
            ip=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f"Estado de Pago {edp.numero_edp} actualizado a '{edp.get_estado_display()}'.")
        return redirect('estados-de-pago-lista')


@method_decorator(login_required, name='dispatch')
class EstadoDePagoAnularView(View):
    """Anular formalmente un Estado de Pago sin borrar el registro."""
    def post(self, request, pk):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso denegado.')
            return redirect('dashboard')

        from .models import EstadoDePago
        edp = get_object_or_404(EstadoDePago, pk=pk)
        motivo = request.POST.get('motivo', 'Anulado por gestión administrativa').strip()

        estado_anterior = edp.get_estado_display()
        edp.estado = 'anulado'
        edp.observaciones = f"{edp.observaciones}\n[ANULADO]: {motivo}".strip()
        edp.save()

        from apps.usuarios.models import AuditLog
        AuditLog.registrar(
            usuario=request.user,
            accion='modificacion',
            modelo='EstadoDePago',
            registro_id=edp.numero_edp,
            campo='estado',
            valor_anterior=estado_anterior,
            valor_nuevo='Anulado',
            detalles=f"Estado de Pago {edp.numero_edp} anulado sin borrar. Motivo: {motivo}",
            ip=request.META.get('REMOTE_ADDR')
        )

        messages.warning(request, f"Estado de Pago {edp.numero_edp} ha sido ANULADO.")
        return redirect('estados-de-pago-lista')


@method_decorator(login_required, name='dispatch')
class EstadoDePagoEliminarView(View):
    """Eliminación física permanente de un Estado de Pago."""
    def post(self, request, pk):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso denegado.')
            return redirect('dashboard')

        from .models import EstadoDePago
        edp = get_object_or_404(EstadoDePago, pk=pk)
        num = edp.numero_edp
        edp.delete()

        from apps.usuarios.models import AuditLog
        AuditLog.registrar(
            usuario=request.user,
            accion='eliminacion',
            modelo='EstadoDePago',
            registro_id=num,
            campo='eliminado',
            valor_anterior=num,
            valor_nuevo='Eliminado',
            detalles=f"Registro de Estado de Pago {num} eliminado permanentemente.",
            ip=request.META.get('REMOTE_ADDR')
        )

        messages.info(request, f"Estado de Pago {num} eliminado permanentemente.")
        return redirect('estados-de-pago-lista')


@method_decorator(login_required, name='dispatch')
class TarifaEmpresaGestionView(View):
    """Gestión de tarifarios comerciales personalizados por cliente y material."""
    template_name = 'empresas/tarifas.html'

    def get(self, request):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso restringido a Gerencia.')
            return redirect('dashboard')

        from .models import Empresa, TarifaEmpresa
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        tarifas = TarifaEmpresa.objects.all().select_related('empresa')
        return render(request, self.template_name, {'empresas': empresas, 'tarifas': tarifas})

    def post(self, request):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            return redirect('dashboard')

        empresa_id = request.POST.get('empresa_id')
        modulo     = request.POST.get('modulo', 'reciclables')
        material   = request.POST.get('tipo_material', '').strip().lower()
        precio_raw = request.POST.get('precio_unitario', '0')
        unidad     = request.POST.get('unidad_medida', 'kg').strip()

        try:
            from decimal import Decimal
            from .models import Empresa, TarifaEmpresa, actualizar_o_crear_edp_empresa
            precio = Decimal(precio_raw)
            empresa = Empresa.objects.get(pk=empresa_id)

            tarifa, created = TarifaEmpresa.objects.update_or_create(
                empresa=empresa,
                modulo=modulo,
                tipo_material=material,
                defaults={
                    'precio_unitario': precio,
                    'unidad_medida': unidad,
                }
            )

            # Auto-actualizar/generar el Estado de Pago de la empresa al cambiar tarifario
            edp = actualizar_o_crear_edp_empresa(empresa, usuario=request.user)

            from apps.usuarios.models import AuditLog
            AuditLog.registrar(
                usuario=request.user,
                accion='creacion' if created else 'modificacion',
                modelo='TarifaEmpresa',
                registro_id=f"{empresa.nombre}-{material}",
                campo='precio_unitario',
                valor_anterior='0',
                valor_nuevo=str(precio),
                detalles=f"Tarifa de {material.upper()} para {empresa.nombre} configurada a ${precio}/{unidad}. Estado de Pago #{edp.numero_edp} recalculado automáticamente.",
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f"Tarifa de {material.upper()} para {empresa.nombre} configurada a ${precio:,.0f}/{unidad}. Estado de Pago #{edp.numero_edp} actualizado automáticamente.")
        except Exception as e:
            messages.error(request, f"Error al guardar tarifa: {str(e)}")

        return redirect('tarifas-empresa')


@method_decorator(login_required, name='dispatch')
class APITarifasEmpresaView(View):
    """API en tiempo real para retornar el tarifario configurado de una empresa en JSON."""
    def get(self, request, pk):
        from django.http import JsonResponse
        from .models import Empresa, TarifaEmpresa
        try:
            empresa = Empresa.objects.get(pk=pk)
            tarifas = TarifaEmpresa.objects.filter(empresa=empresa)
            tarifas_dict = {}
            for t in tarifas:
                tarifas_dict[t.tipo_material.lower()] = {
                    'modulo': t.modulo,
                    'precio_unitario': float(t.precio_unitario),
                    'unidad_medida': t.unidad_medida,
                }
            return JsonResponse({
                'success': True,
                'empresa_id': empresa.pk,
                'empresa_nombre': empresa.nombre,
                'tarifas': tarifas_dict,
            })
        except Empresa.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Empresa no encontrada'}, status=404)




