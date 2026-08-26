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

        modulos        = request.POST.getlist('modulo[]')
        if not modulos and request.POST.get('modulo'):
            modulos = [request.POST.get('modulo')]

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

        otro_servicio_detalle = request.POST.get('otro_servicio_detalle', '').strip()
        if otro_servicio_detalle and ('otros' in modulos or tipo_material == 'otros'):
            if tipo_material == 'otros':
                tipo_material = f"Otros ({otro_servicio_detalle[:40]})"
            descripcion = f"[{otro_servicio_detalle}] {descripcion}".strip()

        errores = []
        if not modulos:
            errores.append('Debes seleccionar al menos un módulo de residuo.')
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

        from datetime import datetime, timedelta
        try:
            fecha_solicitada = datetime.fromisoformat(fecha_str)
        except ValueError:
            fecha_solicitada = timezone.now()

        repetir_servicio = request.POST.get('repetir_servicio') == 'si'
        frecuencia_recurrencia = request.POST.get('frecuencia_recurrencia', 'semanal')
        try:
            total_repeticiones = int(request.POST.get('total_repeticiones', '1')) if repetir_servicio else 1
            total_repeticiones = max(1, min(total_repeticiones, 24))
        except (ValueError, TypeError):
            total_repeticiones = 1

        def calcular_fecha_recurrente(fecha_base, frecuencia, n_iter):
            if n_iter == 0:
                return fecha_base
            if frecuencia == 'semanal':
                return fecha_base + timedelta(days=7 * n_iter)
            elif frecuencia == 'quincenal':
                return fecha_base + timedelta(days=14 * n_iter)
            elif frecuencia == 'mensual':
                year = fecha_base.year + (fecha_base.month + n_iter - 1) // 12
                month = (fecha_base.month + n_iter - 1) % 12 + 1
                day = min(fecha_base.day, 28)
                return fecha_base.replace(year=year, month=month, day=day)
            return fecha_base + timedelta(days=7 * n_iter)

        num_modulos = len(modulos)
        total_por_modulo = total_est / Decimal(num_modulos) if num_modulos > 0 else total_est

        solicitudes_creadas = []
        for rep in range(total_repeticiones):
            fecha_iter = calcular_fecha_recurrente(fecha_solicitada, frecuencia_recurrencia, rep)
            obs_iter = observaciones
            if repetir_servicio and total_repeticiones > 1:
                prefix = f"[Agendamiento Programado {rep + 1}/{total_repeticiones}]"
                obs_iter = f"{prefix} {observaciones}".strip() if observaciones else prefix

            for mod in modulos:
                solicitud = SolicitudRecoleccion.objects.create(
                    empresa=empresa,
                    modulo=mod,
                    tipo_material=tipo_material,
                    cantidad_estimada=cant_est,
                    unidad_medida=unidad_med,
                    precio_unitario=precio_u,
                    total_estimado=total_por_modulo,
                    descripcion=descripcion,
                    direccion_recoleccion=direccion,
                    fecha_solicitada=fecha_iter,
                    observaciones=obs_iter,
                    creado_por=request.user,
                )
                solicitudes_creadas.append(solicitud)

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
        modulos       = request.POST.getlist('modulo[]')
        if not modulos and request.POST.get('modulo'):
            modulos = [request.POST.get('modulo')]

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

        otro_servicio_detalle = request.POST.get('otro_servicio_detalle', '').strip()
        if otro_servicio_detalle and ('otros' in modulos or tipo_material == 'otros'):
            if tipo_material == 'otros':
                tipo_material = f"Otros ({otro_servicio_detalle[:40]})"
            descripcion = f"[{otro_servicio_detalle}] {descripcion}".strip()

        errores = []
        if not empresa_id:   errores.append('Selecciona una empresa.')
        if not modulos:      errores.append('Debes seleccionar al menos un módulo.')
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

        from datetime import datetime, timedelta
        try:
            fecha_solicitada = datetime.fromisoformat(fecha_str)
        except ValueError:
            fecha_solicitada = timezone.now()

        repetir_servicio = request.POST.get('repetir_servicio') == 'si'
        frecuencia_recurrencia = request.POST.get('frecuencia_recurrencia', 'semanal')
        try:
            total_repeticiones = int(request.POST.get('total_repeticiones', '1')) if repetir_servicio else 1
            total_repeticiones = max(1, min(total_repeticiones, 24))
        except (ValueError, TypeError):
            total_repeticiones = 1

        def calcular_fecha_recurrente(fecha_base, frecuencia, n_iter):
            if n_iter == 0:
                return fecha_base
            if frecuencia == 'semanal':
                return fecha_base + timedelta(days=7 * n_iter)
            elif frecuencia == 'quincenal':
                return fecha_base + timedelta(days=14 * n_iter)
            elif frecuencia == 'mensual':
                year = fecha_base.year + (fecha_base.month + n_iter - 1) // 12
                month = (fecha_base.month + n_iter - 1) % 12 + 1
                day = min(fecha_base.day, 28)
                return fecha_base.replace(year=year, month=month, day=day)
            return fecha_base + timedelta(days=7 * n_iter)

        num_modulos = len(modulos)
        total_por_modulo = total_est / Decimal(num_modulos) if num_modulos > 0 else total_est

        solicitudes_creadas = []
        for rep in range(total_repeticiones):
            fecha_iter = calcular_fecha_recurrente(fecha_solicitada, frecuencia_recurrencia, rep)
            obs_iter = observaciones
            if repetir_servicio and total_repeticiones > 1:
                prefix = f"[Agendamiento Programado {rep + 1}/{total_repeticiones}]"
                obs_iter = f"{prefix} {observaciones}".strip() if observaciones else prefix

            for mod in modulos:
                solicitud = SolicitudRecoleccion.objects.create(
                    empresa=empresa,
                    modulo=mod,
                    tipo_material=tipo_material,
                    cantidad_estimada=cant_est,
                    unidad_medida=unidad_med,
                    precio_unitario=precio_u,
                    total_estimado=total_por_modulo,
                    descripcion=descripcion,
                    direccion_recoleccion=direccion,
                    fecha_solicitada=fecha_iter,
                    observaciones=obs_iter,
                    creado_por=request.user,
                )
                solicitudes_creadas.append(solicitud)

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
        
        import calendar
        from django.utils import timezone
        from .models import EstadoDePago, Empresa, actualizar_o_crear_edp_empresa

        today = timezone.now().date()
        
        # Obtener mes y año seleccionados (por defecto mes y año actual)
        try:
            mes_sel = int(request.GET.get('mes', today.month))
            anio_sel = int(request.GET.get('anio', today.year))
        except (ValueError, TypeError):
            mes_sel = today.month
            anio_sel = today.year

        MESES_NOMBRE = [
            (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
            (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
            (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
        ]

        _, last_day = calendar.monthrange(anio_sel, mes_sel)
        p_inicio = today.replace(year=anio_sel, month=mes_sel, day=1)
        p_fin = today.replace(year=anio_sel, month=mes_sel, day=last_day)

        # Si se solicita generar o actualizar EDPs de todas las empresas para este mes
        if request.GET.get('generar') == '1':
            empresas_aprobadas = Empresa.objects.filter(estado='aprobada', activa=True)
            cnt = 0
            for emp in empresas_aprobadas:
                actualizar_o_crear_edp_empresa(emp, periodo_inicio=p_inicio, periodo_fin=p_fin, usuario=request.user)
                cnt += 1
            messages.success(request, f"Se han generado/actualizado los Estados de Pago para {cnt} empresa(s) en {MESES_NOMBRE[mes_sel-1][1]} {anio_sel}.")

        # Buscar EDPs del mes y año seleccionados
        edps = EstadoDePago.objects.filter(
            periodo_inicio__year=anio_sel,
            periodo_inicio__month=mes_sel
        ).select_related('empresa').order_by('-fecha_creacion')

        # Totales consolidados del mes
        total_neto_mes  = sum(e.subtotal_neto for e in edps)
        total_iva_mes   = sum(e.iva for e in edps)
        total_bruto_mes = sum(e.total_bruto for e in edps)

        return render(request, self.template_name, {
            'edps': edps,
            'mes_sel': mes_sel,
            'anio_sel': anio_sel,
            'meses_lista': MESES_NOMBRE,
            'nombre_mes_sel': MESES_NOMBRE[mes_sel-1][1],
            'total_neto_mes': total_neto_mes,
            'total_iva_mes': total_iva_mes,
            'total_bruto_mes': total_bruto_mes,
            'anios_lista': [today.year - 1, today.year, today.year + 1],
        })


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

            grupos = {}

            for s in servicios_qs:
                reg = s.get_registro()
                cant = Decimal('1')
                unid = 'servicio'
                desc_base = f"Servicio de Retiro — {s.get_modulo_display()}"
                mat_key = s.modulo

                # Tarifas por defecto si no hay tarifa personalizada
                tarifa = Decimal('150000')
                if s.modulo == 'rsd': tarifa = Decimal('150000')
                elif s.modulo == 'escombros': tarifa = Decimal('180000')
                elif s.modulo == 'reciclables': tarifa = Decimal('150000')

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
                            desc_base = f"Reciclaje ({mat_key.upper()})"

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

                fecha_obj = s.fecha_retiro_real.date() if s.fecha_retiro_real else (s.fecha_solicitud.date() if s.fecha_solicitud else timezone.now().date())
                fecha_str = fecha_obj.strftime("%d/%m/%Y")

                key = (desc_base, tarifa, unid)
                if key not in grupos:
                    grupos[key] = {
                        'modulo': s.get_modulo_display(),
                        'descripcion': desc_base,
                        'tarifa': tarifa,
                        'unidad': unid,
                        'cantidad': Decimal('0'),
                        'fechas': [],
                        'servicio_obj': s,
                        'fecha_obj': fecha_obj,
                    }
                grupos[key]['cantidad'] += cant
                if fecha_str not in grupos[key]['fechas']:
                    grupos[key]['fechas'].append(fecha_str)

            total_calculado = Decimal('0')

            for item in grupos.values():
                fechas_texto = ", ".join(item['fechas'])
                sub_item = item['cantidad'] * item['tarifa']
                total_calculado += sub_item

                DetalleEstadoDePago.objects.create(
                    estado_de_pago=edp,
                    servicio=item['servicio_obj'],
                    fecha_servicio=item['fecha_obj'],
                    fechas_texto=fechas_texto,
                    modulo=item['modulo'],
                    descripcion=item['descripcion'],
                    cantidad=item['cantidad'],
                    unidad_medida=item['unidad'],
                    tarifa_unitaria=item['tarifa'],
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

        from .models import EstadoDePago, actualizar_o_crear_edp_empresa
        edp = get_object_or_404(EstadoDePago, pk=pk)

        # Si el EDP tiene detalles antiguos sin agrupar, recalcular automáticamente para agruparlos
        if edp.detalles.filter(fechas_texto__isnull=True).exists():
            actualizar_o_crear_edp_empresa(edp.empresa, periodo_inicio=edp.periodo_inicio, periodo_fin=edp.periodo_fin, usuario=request.user)
            edp.refresh_from_db()

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

        empresa_id   = request.POST.get('empresa_id')
        modulos      = request.POST.getlist('modulo[]')   # puede ser 1, 2, 3 u otros módulos
        otro_nombre  = request.POST.get('otro_servicio_nombre', '').strip()
        material_raw = request.POST.get('tipo_material', 'servicio').strip() or 'servicio'
        precio_raw   = request.POST.get('precio_unitario', '0')
        unidad       = request.POST.get('unidad_medida', 'servicio').strip() or 'servicio'

        if not modulos:
            messages.error(request, 'Debes seleccionar al menos un módulo.')
            return redirect('tarifas-empresa')

        try:
            from decimal import Decimal
            from .models import Empresa, TarifaEmpresa, actualizar_o_crear_edp_empresa
            precio  = Decimal(precio_raw)
            empresa = Empresa.objects.get(pk=empresa_id)

            guardados = []
            for modulo in modulos:
                mat_key = material_raw.lower()
                if modulo == 'otros' and otro_nombre:
                    mat_key = otro_nombre

                tarifa, created = TarifaEmpresa.objects.update_or_create(
                    empresa=empresa,
                    modulo=modulo,
                    tipo_material=mat_key,
                    defaults={
                        'precio_unitario': precio,
                        'unidad_medida': unidad,
                    }
                )
                guardados.append(modulo)

            # Auto-actualizar el EDP de la empresa
            edp = actualizar_o_crear_edp_empresa(empresa, usuario=request.user)

            modulos_label = ', '.join({
                'reciclables': 'Reciclables',
                'rsd': 'RSD',
                'escombros': 'RESCON/Escombros',
                'otros': f'Otros ({otro_nombre or "Servicio Personalizado"})',
            }.get(m, m.upper()) for m in guardados)

            from apps.usuarios.models import AuditLog
            AuditLog.registrar(
                usuario=request.user,
                accion='configuracion',
                modelo='TarifaEmpresa',
                registro_id=f"{empresa.nombre}-{otro_nombre or material_raw}",
                campo='precio_unitario',
                valor_anterior='0',
                valor_nuevo=str(precio),
                detalles=f"Tarifas de {modulos_label} para {empresa.nombre} configuradas a ${precio:,.0f}/{unidad}. Estado de Pago #{edp.numero_edp} recalculado.",
                ip=request.META.get('REMOTE_ADDR')
            )

            messages.success(request, f"Tarifa de ${precio:,.0f}/{unidad} guardada para {modulos_label} — {empresa.nombre}. EDP #{edp.numero_edp} actualizado.")
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


# ─── Crear Empresa (Admin directo) ───────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class EmpresaCrearAdminView(View):
    """Vista de creación rápida de empresa para administradores (sin registro público)."""
    template_name = 'empresas/crear_empresa_admin.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')
        return render(request, self.template_name, {'rubros': Empresa.RUBROS, 'estados': Empresa.ESTADOS})

    def post(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')

        nombre          = request.POST.get('nombre', '').strip()
        rut_empresa     = request.POST.get('rut_empresa', '').strip().upper()
        email_contacto  = request.POST.get('email_contacto', '').strip()
        telefono        = request.POST.get('telefono', '').strip()
        direccion       = request.POST.get('direccion', '').strip()
        rubro           = request.POST.get('rubro', 'otro')
        rubro_otro      = request.POST.get('rubro_otro', '').strip()
        nombre_contacto = request.POST.get('nombre_contacto', '').strip()
        cargo_contacto  = request.POST.get('cargo_contacto', '').strip()
        logo            = request.FILES.get('logo')
        estado_val      = request.POST.get('estado', 'pendiente')

        # Usuario de acceso (opcional en creación admin)
        crear_usuario   = request.POST.get('crear_usuario') == '1'
        rut_usuario     = request.POST.get('rut_usuario', '').strip().upper()
        password        = request.POST.get('password', '')

        # Contactos segmentados (names con índice desde JS: contacto_nombre_N, etc.)
        indices = request.POST.getlist('contacto_idx')

        errores = []
        if not nombre:        errores.append('El nombre de la empresa es obligatorio.')
        if not rut_empresa:   errores.append('El RUT de la empresa es obligatorio.')
        if not email_contacto: errores.append('El email de contacto es obligatorio.')
        if Empresa.objects.filter(rut=rut_empresa).exists():
            errores.append('Ya existe una empresa registrada con ese RUT.')
        if crear_usuario:
            if not rut_usuario: errores.append('El RUT del usuario de acceso es obligatorio.')
            elif Usuario.objects.filter(rut=rut_usuario).exists():
                errores.append('Ya existe un usuario con ese RUT.')
            if not password or len(password) < 6:
                errores.append('La contraseña debe tener al menos 6 caracteres.')

        # Validar contactos: nombre y email obligatorios por índice
        for i, idx in enumerate(indices):
            cn = request.POST.get(f'contacto_nombre_{idx}', '').strip()
            ce = request.POST.get(f'contacto_email_{idx}', '').strip()
            if cn and not ce:
                errores.append(f'El contacto #{i+1} ({cn}) necesita un email válido.')
            elif ce and not cn:
                errores.append(f'El contacto #{i+1} con email {ce} necesita un nombre.')

        if errores:
            return render(request, self.template_name, {
                'errores': errores, 'form_data': request.POST,
                'rubros': Empresa.RUBROS, 'estados': Empresa.ESTADOS,
            })

        empresa = Empresa.objects.create(
            nombre=nombre, rut=rut_empresa,
            email_contacto=email_contacto, telefono=telefono,
            direccion=direccion, rubro=rubro,
            rubro_otro=rubro_otro if rubro == 'otro' else None,
            nombre_contacto=nombre_contacto,
            cargo_contacto=cargo_contacto,
            logo=logo if logo else None,
            estado=estado_val,
        )

        if estado_val == 'aprobada':
            empresa.fecha_aprobacion = timezone.now()
            empresa.save()

        if crear_usuario and rut_usuario and password:
            Usuario.objects.create_user(
                rut=rut_usuario, password=password,
                nombre=nombre_contacto or nombre,
                apellido='',
                email=email_contacto, telefono=telefono,
                rol='empresa',
                estado='aprobado' if estado_val == 'aprobada' else 'pendiente',
                empresa=empresa,
            )

        # Guardar contactos segmentados (usando nombres de campo con índice)
        from .models import ContactoEmpresa
        tot_contactos = 0
        for idx in indices:
            cn = request.POST.get(f'contacto_nombre_{idx}', '').strip()
            ce = request.POST.get(f'contacto_email_{idx}', '').strip()
            if not cn or not ce:
                continue
            ContactoEmpresa.objects.create(
                empresa=empresa,
                nombre=cn,
                cargo=request.POST.get(f'contacto_cargo_{idx}', '').strip(),
                email=ce,
                recibe_certificados=  bool(request.POST.get(f'contacto_cert_{idx}')),
                recibe_estados_pago=  bool(request.POST.get(f'contacto_edp_{idx}')),
                recibe_reportes=      bool(request.POST.get(f'contacto_rep_{idx}')),
                recibe_notificaciones=bool(request.POST.get(f'contacto_notif_{idx}', '1')),
            )
            tot_contactos += 1

        from apps.usuarios.models import AuditLog
        AuditLog.registrar(
            usuario=request.user,
            accion='creacion',
            modelo='Empresa',
            registro_id=empresa.pk,
            detalles=f"Empresa '{nombre}' creada directamente por admin (estado: {estado_val}, contactos: {tot_contactos}).",
            ip=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'Empresa "{nombre}" creada exitosamente.')
        return redirect('empresa-list')


