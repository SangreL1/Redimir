"""
VISTAS DE SERVICIOS — REDIMIR
Flujo: Crear solicitud → Programar → Asignar → Registrar (operador) → Validar → Emitir doc
"""
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from django.http import JsonResponse

from .models import (
    Servicio, RegistroRSD, FotoRegistroRSD,
    RegistroEscombros, FotoRegistroEscombros,
    RegistroReciclables, FotoRegistroReciclables,
)
from apps.usuarios.models import Usuario
from apps.empresas.models import Empresa


def _es_admin(user):
    return user.rol == 'admin' or user.is_staff

def _es_operador(user):
    return user.rol in ('recolector', 'operador')


# ─── CREAR SOLICITUD ─────────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class CrearServicioView(View):
    """Admin o empresa crean una solicitud de retiro con módulo obligatorio."""
    template_name = 'servicios/crear.html'

    def get(self, request):
        if not (_es_admin(request.user) or request.user.rol == 'empresa' or _es_operador(request.user)):
            messages.error(request, 'Sin permisos para crear servicios.')
            return redirect('dashboard')
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        operadores = Usuario.objects.filter(rol__in=['recolector','operador'], estado='aprobado', is_active=True)
        return render(request, self.template_name, {
            'empresas': empresas,
            'operadores': operadores,
        })

    def post(self, request):
        empresa_id     = request.POST.get('empresa')
        modulo         = request.POST.get('modulo')
        direccion      = request.POST.get('direccion', '').strip()
        contacto       = request.POST.get('contacto_responsable', '').strip()
        telefono       = request.POST.get('telefono_contacto', '').strip()
        cantidad_est   = request.POST.get('cantidad_estimada') or None
        unidad_est     = request.POST.get('unidad_estimada', 'kg')
        fecha_prog_str = request.POST.get('fecha_programada')
        ventana_ini    = request.POST.get('ventana_inicio') or None
        ventana_fin    = request.POST.get('ventana_fin') or None
        operador_id    = request.POST.get('operador') or None
        observaciones  = request.POST.get('observaciones', '').strip()

        errores = []
        if not empresa_id: errores.append('Selecciona una empresa.')
        if not modulo:     errores.append('Selecciona el módulo de residuo.')
        if not direccion or len(direccion) < 10:
            errores.append('La dirección debe tener al menos 10 caracteres.')
        if modulo not in dict(Servicio.MODULOS):
            errores.append('Módulo inválido.')

        if errores:
            empresas   = Empresa.objects.filter(estado='aprobada', activa=True)
            operadores = Usuario.objects.filter(rol__in=['recolector','operador'], estado='aprobado', is_active=True)
            return render(request, self.template_name, {
                'errores': errores, 'form_data': request.POST,
                'empresas': empresas, 'operadores': operadores,
            })

        empresa = get_object_or_404(Empresa, pk=empresa_id)

        # Si es empresa la que solicita, usar su propia empresa
        if request.user.rol == 'empresa':
            empresa = request.user.empresa

        fecha_prog = None
        if fecha_prog_str:
            try:
                from datetime import datetime
                fecha_prog = datetime.strptime(fecha_prog_str, '%Y-%m-%dT%H:%M')
                fecha_prog = timezone.make_aware(fecha_prog)
            except Exception:
                pass

        operador = None
        if operador_id:
            try:
                operador = Usuario.objects.get(pk=operador_id)
            except Usuario.DoesNotExist:
                pass

        auto_validar = request.POST.get('auto_validar') == '1' and _es_admin(request.user)

        estado_inicial = 'programado' if fecha_prog else 'solicitado'
        if operador:
            estado_inicial = 'asignado'
        if auto_validar:
            estado_inicial = 'validado'

        servicio = Servicio.objects.create(
            empresa=empresa,
            modulo=modulo,
            estado=estado_inicial,
            direccion=direccion,
            contacto_responsable=contacto,
            telefono_contacto=telefono,
            cantidad_estimada=cantidad_est,
            unidad_estimada=unidad_est,
            fecha_programada=fecha_prog,
            fecha_retiro_real=timezone.now() if auto_validar else None,
            ventana_inicio=ventana_ini,
            ventana_fin=ventana_fin,
            operador=operador,
            usuario_creador=request.user,
            usuario_validador=request.user if auto_validar else None,
            fecha_validacion=timezone.now() if auto_validar else None,
            observaciones=observaciones,
        )

        if auto_validar:
            cant_val = float(cantidad_est) if cantidad_est else 100.0
            ticket_val = request.POST.get('ticket_externo', '').strip() or f"AUTO-{servicio.pk:04d}"
            if modulo == 'rsd':
                RegistroRSD.objects.create(
                    servicio=servicio,
                    tipo_residuo='rsd',
                    cantidad_kg=cant_val,
                    ticket_externo=ticket_val,
                    destino_receptor='socsal',
                    usuario_registro=request.user,
                )
            elif modulo == 'escombros':
                RegistroEscombros.objects.create(
                    servicio=servicio,
                    tipo_residuo='escombros',
                    cantidad=cant_val,
                    unidad=unidad_est if unidad_est in ['m3', 'kg', 'sacos'] else 'm3',
                    ticket_externo=ticket_val,
                    destino_receptor='municipalidad',
                    usuario_registro=request.user,
                )
            elif modulo == 'reciclables':
                reg_rec = RegistroReciclables.objects.create(
                    servicio=servicio,
                    material=request.POST.get('material_reciclable', 'carton'),
                    cantidad_kg=cant_val,
                    destino='gestor',
                    usuario_registro=request.user,
                )
                try:
                    reg_rec.calcular_eco_equivalencia()
                except Exception:
                    pass

        # Auto-generar / actualizar el Estado de Pago de la Empresa
        try:
            from apps.empresas.models import actualizar_o_crear_edp_empresa
            actualizar_o_crear_edp_empresa(empresa, usuario=request.user)
        except Exception as err_edp:
            pass

        # Notificar al operador si está asignado
        if operador and not auto_validar:
            _notificar_operador(servicio, operador)

        if auto_validar:
            messages.success(request, f'✅ Servicio #{servicio.pk} creado y VALIDADO exitosamente ({servicio.get_modulo_display()}). ¡Ya disponible para certificados!')
        else:
            messages.success(request, f'Servicio #{servicio.pk} creado exitosamente ({servicio.get_modulo_display()}).')

        return redirect('servicio-detalle', pk=servicio.pk)


def _notificar_operador(servicio, operador):
    """Crea notificación interna para el operador asignado."""
    from apps.notificaciones.models import Notificacion
    try:
        Notificacion.objects.create(
            usuario=operador,
            tipo='servicio_asignado',
            titulo=f'Nuevo retiro asignado — {servicio.empresa.nombre}',
            mensaje=(
                f'Se te asignó un retiro de {servicio.get_modulo_display()} '
                f'en {servicio.direccion}. '
                f'Fecha: {servicio.fecha_programada.strftime("%d/%m/%Y") if servicio.fecha_programada else "Por confirmar"}'
            ),
            url_destino=f'/servicios/{servicio.pk}/',
        )
    except Exception:
        pass


# ─── LISTA DE SERVICIOS ───────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class ListaServiciosView(View):
    template_name = 'servicios/lista.html'

    def get(self, request):
        user = request.user

        if _es_admin(user):
            qs = Servicio.objects.select_related('empresa', 'operador')
        elif _es_operador(user):
            # Operador solo ve sus servicios asignados
            qs = Servicio.objects.filter(operador=user).select_related('empresa')
        elif user.rol == 'empresa' and user.empresa:
            qs = Servicio.objects.filter(empresa=user.empresa).select_related('empresa')
        else:
            qs = Servicio.objects.none()

        # Filtros
        estado_f  = request.GET.get('estado', '')
        modulo_f  = request.GET.get('modulo', '')
        empresa_f = request.GET.get('empresa', '')
        q         = request.GET.get('q', '').strip()

        if estado_f:
            qs = qs.filter(estado=estado_f)
        if modulo_f:
            qs = qs.filter(modulo=modulo_f)
        if empresa_f and _es_admin(user):
            qs = qs.filter(empresa_id=empresa_f)
        if q:
            qs = qs.filter(
                Q(empresa__nombre__icontains=q) |
                Q(direccion__icontains=q) |
                Q(operador__nombre__icontains=q)
            )

        qs = qs.order_by('-fecha_solicitud')

        # Para filtros del template
        empresas = Empresa.objects.filter(activa=True) if _es_admin(user) else []

        return render(request, self.template_name, {
            'servicios':  qs,
            'estados':    Servicio.ESTADOS,
            'modulos':    Servicio.MODULOS,
            'empresas':   empresas,
            'estado_sel': estado_f,
            'modulo_sel': modulo_f,
            'empresa_sel': empresa_f,
            'q':          q,
            'total':      qs.count(),
            'hoy':        timezone.now().date(),
            'es_admin':   _es_admin(user),
        })


# ─── DETALLE DE SERVICIO ──────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class DetalleServicioView(View):
    template_name = 'servicios/detalle.html'

    def get(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk, is_active=True)

        # Verificar acceso
        user = request.user
        if not _es_admin(user):
            if _es_operador(user) and servicio.operador != user:
                messages.error(request, 'No tienes acceso a este servicio.')
                return redirect('servicios-lista')
            if user.rol == 'empresa' and (not user.empresa or servicio.empresa != user.empresa):
                messages.error(request, 'No tienes acceso a este servicio.')
                return redirect('dashboard')

        registro = servicio.get_registro()
        operadores = Usuario.objects.filter(
            rol__in=['recolector','operador'], estado='aprobado', is_active=True
        ) if _es_admin(user) else []

        return render(request, self.template_name, {
            'servicio':   servicio,
            'registro':   registro,
            'operadores': operadores,
            'es_admin':   _es_admin(user),
        })

    def post(self, request, pk):
        """Admin acciones: asignar operador, cambiar estado."""
        if not _es_admin(request.user):
            return redirect('dashboard')

        servicio = get_object_or_404(Servicio, pk=pk, is_active=True)
        accion = request.POST.get('accion', '')

        if accion == 'asignar_operador':
            op_id = request.POST.get('operador_id')
            fecha_str = request.POST.get('fecha_programada')
            if op_id:
                try:
                    op = Usuario.objects.get(pk=op_id)
                    servicio.operador = op
                    if fecha_str:
                        from datetime import datetime
                        fp = datetime.strptime(fecha_str, '%Y-%m-%dT%H:%M')
                        servicio.fecha_programada = timezone.make_aware(fp)
                    servicio.estado = 'asignado'
                    servicio.save()
                    _notificar_operador(servicio, op)
                    messages.success(request, f'Operador {op.nombre_completo} asignado.')
                except Exception as e:
                    messages.error(request, f'Error: {e}')

        elif accion == 'cambiar_estado':
            nuevo_estado = request.POST.get('estado')
            estados_validos = dict(Servicio.ESTADOS).keys()
            if nuevo_estado in estados_validos:
                servicio.estado = nuevo_estado
                servicio.save()
                messages.success(request, f'Estado actualizado a: {servicio.get_estado_display()}')

        return redirect('servicio-detalle', pk=pk)


# ─── REGISTRAR RETIRO (OPERADOR — MOBILE) ────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class RegistrarRetiroView(View):
    """Flujo paso a paso para el operador. Mobile-first."""

    def get(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk, is_active=True)

        if not _es_operador(request.user) and not _es_admin(request.user):
            messages.error(request, 'Sin permisos.')
            return redirect('dashboard')

        if _es_operador(request.user) and servicio.operador != request.user:
            messages.error(request, 'Este servicio no está asignado a ti.')
            return redirect('servicios-lista')

        if servicio.modulo == 'rsd':
            template = 'servicios/registrar_rsd.html'
        elif servicio.modulo == 'escombros':
            template = 'servicios/registrar_escombros.html'
        else:
            template = 'servicios/registrar_reciclables.html'

        return render(request, template, {'servicio': servicio})

    def post(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk, is_active=True)

        if not _es_operador(request.user) and not _es_admin(request.user):
            return redirect('dashboard')

        # Validar fotos
        fotos = request.FILES.getlist('fotos')
        if not fotos:
            messages.error(request, '⚠️ Debes subir al menos una foto de evidencia.')
            if servicio.modulo == 'rsd':
                return render(request, 'servicios/registrar_rsd.html', {'servicio': servicio, 'error_foto': True})
            elif servicio.modulo == 'escombros':
                return render(request, 'servicios/registrar_escombros.html', {'servicio': servicio, 'error_foto': True})
            else:
                return render(request, 'servicios/registrar_reciclables.html', {'servicio': servicio, 'error_foto': True})

        ubicacion = request.POST.get('ubicacion_gps', '')
        observaciones = request.POST.get('observaciones', '').strip()

        try:
            if servicio.modulo == 'rsd':
                registro = self._crear_registro_rsd(request, servicio, ubicacion, observaciones)
                self._guardar_fotos_rsd(fotos, registro)

            elif servicio.modulo == 'escombros':
                registro = self._crear_registro_escombros(request, servicio, ubicacion, observaciones)
                self._guardar_fotos_escombros(fotos, registro)

            else:  # reciclables
                registro = self._crear_registro_reciclables(request, servicio, ubicacion, observaciones)
                self._guardar_fotos_reciclables(fotos, registro)
                registro.calcular_eco_equivalencia()

            # Actualizar estado servicio
            servicio.estado = 'pendiente_validacion'
            servicio.fecha_retiro_real = timezone.now()
            servicio.save()

            # Notificar a admin
            self._notificar_admin_pendiente(servicio, request.user)

            messages.success(request, '✅ Retiro registrado exitosamente. Pendiente de validación.')
            return redirect('registro-exitoso', pk=servicio.pk)

        except Exception as e:
            messages.error(request, f'Error al guardar el registro: {e}')
            return redirect('registrar-retiro', pk=pk)

    def _crear_registro_rsd(self, request, servicio, ubicacion, observaciones):
        return RegistroRSD.objects.create(
            servicio=servicio,
            tipo_residuo=request.POST.get('tipo_residuo', 'rsd'),
            cantidad_kg=request.POST.get('cantidad_kg'),
            ticket_externo=request.POST.get('ticket_externo', ''),
            destino_receptor=request.POST.get('destino_receptor', 'socsal'),
            destino_otro=request.POST.get('destino_otro', ''),
            observaciones=observaciones,
            usuario_registro=request.user,
            ubicacion_gps=ubicacion,
        )

    def _crear_registro_escombros(self, request, servicio, ubicacion, observaciones):
        return RegistroEscombros.objects.create(
            servicio=servicio,
            tipo_residuo=request.POST.get('tipo_residuo', 'escombros'),
            cantidad=request.POST.get('cantidad'),
            unidad=request.POST.get('unidad', 'm3'),
            ticket_externo=request.POST.get('ticket_externo', ''),
            destino_receptor=request.POST.get('destino_receptor', 'municipalidad'),
            destino_otro=request.POST.get('destino_otro', ''),
            observaciones=observaciones,
            usuario_registro=request.user,
            ubicacion_gps=ubicacion,
        )

    def _crear_registro_reciclables(self, request, servicio, ubicacion, observaciones):
        return RegistroReciclables.objects.create(
            servicio=servicio,
            material=request.POST.get('material', 'carton'),
            cantidad_kg=request.POST.get('cantidad_kg'),
            unidades=request.POST.get('unidades') or None,
            destino=request.POST.get('destino', 'gestor'),
            destino_otro=request.POST.get('destino_otro', ''),
            observaciones=observaciones,
            usuario_registro=request.user,
            ubicacion_gps=ubicacion,
        )

    def _guardar_fotos_rsd(self, fotos, registro):
        for i, f in enumerate(fotos):
            FotoRegistroRSD.objects.create(registro=registro, foto=f, es_principal=(i == 0))

    def _guardar_fotos_escombros(self, fotos, registro):
        for i, f in enumerate(fotos):
            FotoRegistroEscombros.objects.create(registro=registro, foto=f, es_principal=(i == 0))

    def _guardar_fotos_reciclables(self, fotos, registro):
        for i, f in enumerate(fotos):
            FotoRegistroReciclables.objects.create(registro=registro, foto=f, es_principal=(i == 0))

    def _notificar_admin_pendiente(self, servicio, operador):
        from apps.notificaciones.models import Notificacion
        admins = Usuario.objects.filter(rol='admin', is_active=True, estado='aprobado')
        notifs = [
            Notificacion(
                usuario=admin,
                tipo='validacion_pendiente',
                titulo=f'Retiro pendiente de validación — {servicio.empresa.nombre}',
                mensaje=(
                    f'{operador.nombre_completo} completó el retiro #{servicio.pk} '
                    f'de {servicio.get_modulo_display()}. Pendiente de tu validación.'
                ),
                url_destino=f'/validaciones/',
            )
            for admin in admins
        ]
        try:
            Notificacion.objects.bulk_create(notifs)
        except Exception:
            pass


# ─── PANTALLA DE ÉXITO ───────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class RegistroExitosoView(View):
    template_name = 'servicios/registro_exitoso.html'

    def get(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk)
        return render(request, self.template_name, {'servicio': servicio})


# ─── VALIDACIONES (ADMIN) ────────────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class ValidacionesPendientesView(View):
    template_name = 'servicios/validaciones.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'Sin permisos.')
            return redirect('dashboard')

        pendientes = Servicio.objects.filter(
            estado__in=['pendiente_validacion', 'observado'],
            is_active=True,
        ).select_related('empresa', 'operador').order_by('fecha_retiro_real')

        return render(request, self.template_name, {
            'pendientes': pendientes,
            'total':      pendientes.count(),
        })

    def post(self, request):
        if not _es_admin(request.user):
            return redirect('dashboard')

        servicio_id = request.POST.get('servicio_id')
        accion      = request.POST.get('accion')  # validar, observar, rechazar
        observacion = request.POST.get('observacion', '').strip()

        servicio = get_object_or_404(Servicio, pk=servicio_id)

        if accion == 'validar':
            servicio.estado = 'validado'
            servicio.usuario_validador = request.user
            servicio.fecha_validacion  = timezone.now()
            servicio.save()
            _notificar_cliente(servicio, 'validado')

            # Auto-generar / actualizar el Estado de Pago de la Empresa
            try:
                from apps.empresas.models import actualizar_o_crear_edp_empresa
                actualizar_o_crear_edp_empresa(servicio.empresa, usuario=request.user)
            except Exception:
                pass

            messages.success(request, f'✅ Servicio #{servicio.pk} validado correctamente y Estado de Pago actualizado.')

        elif accion == 'observar':
            servicio.estado = 'observado'
            servicio.observacion_admin = observacion
            servicio.usuario_validador = request.user
            servicio.save()
            _notificar_operador_observacion(servicio, observacion)
            messages.warning(request, f'⚠️ Servicio #{servicio.pk} marcado como observado.')

        elif accion == 'rechazar':
            servicio.estado = 'solicitado'  # vuelve a solicitado para re-asignar
            servicio.observacion_admin = observacion
            servicio.save()
            _notificar_operador_rechazo(servicio, observacion)
            messages.error(request, f'❌ Servicio #{servicio.pk} rechazado.')

        return redirect('validaciones')


def _notificar_cliente(servicio, evento):
    """Notifica al usuario empresa cuando el retiro es validado."""
    from apps.notificaciones.models import Notificacion
    try:
        usuario_empresa = servicio.empresa.trabajadores.filter(rol='empresa', is_active=True).first()
        if usuario_empresa:
            Notificacion.objects.create(
                usuario=usuario_empresa,
                tipo='retiro_validado',
                titulo=f'Retiro validado — {servicio.get_modulo_display()}',
                mensaje=f'El retiro #{servicio.pk} fue validado. Pronto recibirás tu certificado.',
                url_destino=f'/servicios/{servicio.pk}/',
            )
    except Exception:
        pass


def _notificar_operador_observacion(servicio, observacion):
    from apps.notificaciones.models import Notificacion
    try:
        if servicio.operador:
            Notificacion.objects.create(
                usuario=servicio.operador,
                tipo='servicio_observado',
                titulo=f'Tu retiro #{servicio.pk} fue observado',
                mensaje=f'Observación: {observacion}',
                url_destino=f'/servicios/{servicio.pk}/',
            )
    except Exception:
        pass


def _notificar_operador_rechazo(servicio, observacion):
    from apps.notificaciones.models import Notificacion
    try:
        if servicio.operador:
            Notificacion.objects.create(
                usuario=servicio.operador,
                tipo='servicio_rechazado',
                titulo=f'Tu registro #{servicio.pk} fue rechazado',
                mensaje=f'Motivo: {observacion}',
                url_destino=f'/servicios/{servicio.pk}/',
            )
    except Exception:
        pass


# ─── EDITAR REGISTRO / SERVICIO ──────────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class EditarServicioRegistroView(View):
    """Permite modificar un servicio y su registro de pesaje/retiro existente."""
    template_name = 'servicios/editar.html'

    def get(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk, is_active=True)
        user = request.user

        if not (_es_admin(user) or (_es_operador(user) and servicio.operador == user) or servicio.usuario_creador == user):
            messages.error(request, 'No tienes permisos para modificar este servicio.')
            return redirect('servicio-detalle', pk=pk)

        registro = servicio.get_registro()
        empresas = Empresa.objects.filter(activa=True) if _es_admin(user) else []
        operadores = Usuario.objects.filter(
            rol__in=['recolector', 'operador'], estado='aprobado', is_active=True
        ) if _es_admin(user) else []

        return render(request, self.template_name, {
            'servicio': servicio,
            'registro': registro,
            'empresas': empresas,
            'operadores': operadores,
            'es_admin': _es_admin(user),
            'tipos_rsd': RegistroRSD.TIPOS_RESIDUO,
            'destinos_rsd': RegistroRSD.DESTINOS,
            'tipos_escombros': RegistroEscombros.TIPOS_RESIDUO,
            'unidades_escombros': RegistroEscombros.UNIDADES,
            'destinos_escombros': RegistroEscombros.DESTINOS,
            'materiales_reciclables': RegistroReciclables.MATERIALES,
            'destinos_reciclables': RegistroReciclables.DESTINOS,
        })

    def post(self, request, pk):
        servicio = get_object_or_404(Servicio, pk=pk, is_active=True)
        user = request.user

        if not (_es_admin(user) or (_es_operador(user) and servicio.operador == user) or servicio.usuario_creador == user):
            messages.error(request, 'No tienes permisos para editar este registro.')
            return redirect('servicio-detalle', pk=pk)

        # 1. Modificar campos de Servicio
        direccion = request.POST.get('direccion', '').strip()
        contacto = request.POST.get('contacto_responsable', '').strip()
        telefono = request.POST.get('telefono_contacto', '').strip()
        cantidad_est = request.POST.get('cantidad_estimada') or None
        unidad_est = request.POST.get('unidad_estimada', 'kg')
        observaciones_srv = request.POST.get('observaciones_servicio', '').strip()

        if direccion:
            servicio.direccion = direccion
        servicio.contacto_responsable = contacto
        servicio.telefono_contacto = telefono
        if cantidad_est:
            try:
                from decimal import Decimal
                servicio.cantidad_estimada = Decimal(str(cantidad_est))
            except Exception:
                pass
        servicio.unidad_estimada = unidad_est
        if observations_srv := observaciones_srv:
            servicio.observaciones = observations_srv

        if _es_admin(user):
            if emp_id := request.POST.get('empresa'):
                try:
                    servicio.empresa = Empresa.objects.get(pk=emp_id)
                except Empresa.DoesNotExist:
                    pass
            if op_id := request.POST.get('operador'):
                try:
                    servicio.operador = Usuario.objects.get(pk=op_id)
                except Usuario.DoesNotExist:
                    pass
            if est := request.POST.get('estado'):
                if est in dict(Servicio.ESTADOS):
                    servicio.estado = est

        servicio.save()

        # 2. Modificar / Crear Registro del Módulo
        registro = servicio.get_registro()
        obs_reg = request.POST.get('observaciones_registro', '').strip()
        ticket_ext = request.POST.get('ticket_externo', '').strip()

        try:
            if servicio.modulo == 'rsd':
                tipo_r = request.POST.get('tipo_residuo', 'rsd')
                cant_kg = request.POST.get('cantidad_kg', '0')
                dest_rec = request.POST.get('destino_receptor', 'socsal')
                dest_otro = request.POST.get('destino_otro', '')

                if registro:
                    registro.tipo_residuo = tipo_r
                    registro.cantidad_kg = cant_kg
                    registro.ticket_externo = ticket_ext
                    registro.destino_receptor = dest_rec
                    registro.destino_otro = dest_otro
                    if obs_reg: registro.observaciones = obs_reg
                    registro.save()
                else:
                    registro = RegistroRSD.objects.create(
                        servicio=servicio,
                        tipo_residuo=tipo_r,
                        cantidad_kg=cant_kg,
                        ticket_externo=ticket_ext,
                        destino_receptor=dest_rec,
                        destino_otro=dest_otro,
                        observaciones=obs_reg,
                        usuario_registro=user,
                    )

            elif servicio.modulo == 'escombros':
                tipo_r = request.POST.get('tipo_residuo', 'escombros')
                cant = request.POST.get('cantidad', '0')
                unid = request.POST.get('unidad', 'm3')
                dest_rec = request.POST.get('destino_receptor', 'municipalidad')
                dest_otro = request.POST.get('destino_otro', '')

                if registro:
                    registro.tipo_residuo = tipo_r
                    registro.cantidad = cant
                    registro.unidad = unid
                    registro.ticket_externo = ticket_ext
                    registro.destino_receptor = dest_rec
                    registro.destino_otro = dest_otro
                    if obs_reg: registro.observaciones = obs_reg
                    registro.save()
                else:
                    registro = RegistroEscombros.objects.create(
                        servicio=servicio,
                        tipo_residuo=tipo_r,
                        cantidad=cant,
                        unidad=unid,
                        ticket_externo=ticket_ext,
                        destino_receptor=dest_rec,
                        destino_otro=dest_otro,
                        observaciones=obs_reg,
                        usuario_registro=user,
                    )

            elif servicio.modulo == 'reciclables':
                mat = request.POST.get('material', 'carton')
                cant_kg = request.POST.get('cantidad_kg', '0')
                unid_val = request.POST.get('unidades') or None
                dest = request.POST.get('destino', 'gestor')
                dest_otro = request.POST.get('destino_otro', '')

                if registro:
                    registro.material = mat
                    registro.cantidad_kg = cant_kg
                    registro.unidades = unid_val
                    registro.destino = dest
                    registro.destino_otro = dest_otro
                    if obs_reg: registro.observaciones = obs_reg
                    registro.save()
                else:
                    registro = RegistroReciclables.objects.create(
                        servicio=servicio,
                        material=mat,
                        cantidad_kg=cant_kg,
                        unidades=unid_val,
                        destino=dest,
                        destino_otro=dest_otro,
                        observaciones=obs_reg,
                        usuario_registro=user,
                    )
                registro.calcular_eco_equivalencia()

            # 3. Eliminar fotos seleccionadas por el usuario
            eliminar_foto_ids = request.POST.getlist('eliminar_foto_ids')
            if eliminar_foto_ids and registro:
                if servicio.modulo == 'rsd':
                    FotoRegistroRSD.objects.filter(pk__in=eliminar_foto_ids, registro=registro).delete()
                elif servicio.modulo == 'escombros':
                    FotoRegistroEscombros.objects.filter(pk__in=eliminar_foto_ids, registro=registro).delete()
                elif servicio.modulo == 'reciclables':
                    FotoRegistroReciclables.objects.filter(pk__in=eliminar_foto_ids, registro=registro).delete()

            # 4. Subir fotos nuevas/reemplazo de evidencia si se incluyen
            fotos_nuevas = request.FILES.getlist('fotos')
            if fotos_nuevas and registro:
                if servicio.modulo == 'rsd':
                    for f in fotos_nuevas:
                        FotoRegistroRSD.objects.create(registro=registro, foto=f)
                elif servicio.modulo == 'escombros':
                    for f in fotos_nuevas:
                        FotoRegistroEscombros.objects.create(registro=registro, foto=f)
                elif servicio.modulo == 'reciclables':
                    for f in fotos_nuevas:
                        FotoRegistroReciclables.objects.create(registro=registro, foto=f)

            # 4. Actualizar Estado de Pago (EDP) de la empresa
            try:
                from apps.empresas.models import actualizar_o_crear_edp_empresa
                actualizar_o_crear_edp_empresa(servicio.empresa, usuario=user)
            except Exception:
                pass

            messages.success(request, f'✅ Servicio y registro #{servicio.pk} modificados correctamente.')
            next_url = request.POST.get('next_url')
            if next_url:
                return redirect(next_url)
            return redirect('servicio-detalle', pk=servicio.pk)

        except Exception as e:
            messages.error(request, f'Error al actualizar el registro: {e}')
            return redirect('servicio-editar', pk=pk)

