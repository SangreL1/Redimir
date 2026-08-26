from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import timedelta

from .models import Usuario
from apps.empresas.models import Empresa


def _es_admin(user):
    return user.rol == 'admin' or user.is_staff


# ─── LOGIN ────────────────────────────────────────────────────────────────────

class LoginPageView(View):
    template_name = 'login.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name)

    def post(self, request):
        rut   = request.POST.get('rut', '').strip().upper()
        password = request.POST.get('password', '')
        tipo  = request.POST.get('tipo', 'trabajador')

        user = authenticate(request, username=rut, password=password)

        if user is None:
            return render(request, self.template_name, {
                'error': 'RUT o contraseña incorrectos.',
                'tipo_activo': tipo,
            })

        if not user.esta_aprobado:
            txt = {
                'pendiente': 'Tu cuenta está pendiente de aprobación.',
                'rechazado': 'Tu cuenta fue rechazada. Contacta al administrador.',
            }.get(user.estado, 'Cuenta no activa.')
            return render(request, self.template_name, {'error': txt, 'tipo_activo': tipo})

        # Validación estricta para usuarios tipo Empresa
        if user.rol == 'empresa':
            if not user.empresa:
                return render(request, self.template_name, {
                    'error': 'La empresa asociada a este usuario fue eliminada. Acceso revocado.',
                    'tipo_activo': tipo,
                })
            if user.empresa.estado != 'aprobada' or not user.empresa.activa:
                return render(request, self.template_name, {
                    'error': 'La empresa asociada a esta cuenta no se encuentra aprobada o activa.',
                    'tipo_activo': tipo,
                })

        login(request, user)
        return redirect('dashboard')


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('login-page')


# ─── REGISTRO: EMPRESA ────────────────────────────────────────────────────────

class RegistroEmpresaView(View):
    template_name = 'registro_empresa.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        return render(request, self.template_name)

    def post(self, request):
        nombre          = request.POST.get('nombre', '').strip()
        rut_empresa     = request.POST.get('rut_empresa', '').strip().upper()
        email_contacto  = request.POST.get('email_contacto', '').strip()
        telefono        = request.POST.get('telefono', '').strip()
        direccion       = request.POST.get('direccion', '').strip()
        rubro           = request.POST.get('rubro', 'otro')
        rubro_otro      = request.POST.get('rubro_otro', '').strip()
        nombre_contacto = request.POST.get('nombre_contacto', '').strip()
        apellido_contacto = request.POST.get('apellido_contacto', '').strip()
        cargo_contacto  = request.POST.get('cargo_contacto', '').strip()
        logo            = request.FILES.get('logo')
        rut_usuario     = request.POST.get('rut_usuario', '').strip().upper()
        password        = request.POST.get('password', '')
        password2       = request.POST.get('password2', '')

        errores = []
        if not nombre:         errores.append('El nombre de la empresa es obligatorio.')
        if not rut_empresa:    errores.append('El RUT de la empresa es obligatorio.')
        if not email_contacto: errores.append('El email de contacto es obligatorio.')
        if not rut_usuario:    errores.append('El RUT del responsable es obligatorio.')
        if not password or len(password) < 6:
            errores.append('La contraseña debe tener al menos 6 caracteres.')
        if password != password2:
            errores.append('Las contraseñas no coinciden.')
        if Empresa.objects.filter(rut=rut_empresa).exists():
            errores.append('Ya existe una empresa registrada con ese RUT.')
        if Usuario.objects.filter(rut=rut_usuario).exists():
            errores.append('Ya existe un usuario con ese RUT.')

        if errores:
            return render(request, self.template_name, {
                'errores': errores, 'form_data': request.POST,
            })

        empresa = Empresa.objects.create(
            nombre=nombre, rut=rut_empresa,
            email_contacto=email_contacto, telefono=telefono,
            direccion=direccion, rubro=rubro,
            rubro_otro=rubro_otro if rubro == 'otro' else None,
            nombre_contacto=f"{nombre_contacto} {apellido_contacto}".strip(),
            cargo_contacto=cargo_contacto,
            logo=logo if logo else None,
            estado='pendiente',
        )

        Usuario.objects.create_user(
            rut=rut_usuario, password=password,
            nombre=nombre_contacto or nombre,
            apellido=apellido_contacto,
            email=email_contacto, telefono=telefono,
            rol='empresa',
            estado='pendiente',
            empresa=empresa,
        )

        return render(request, self.template_name, {'success': True})


# ─── REGISTRO: RECOLECTOR ─────────────────────────────────────────────────────

class RegistroTrabajadorView(View):
    template_name = 'registro_trabajador.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('dashboard')
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        return render(request, self.template_name, {'empresas': empresas})

    def post(self, request):
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        rut      = request.POST.get('rut', '').strip().upper()
        nombre   = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        email    = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        edad     = request.POST.get('edad', None)
        genero   = request.POST.get('genero', '')
        empresa_id = request.POST.get('empresa', None)
        password   = request.POST.get('password', '')
        password2  = request.POST.get('password2', '')

        errores = []
        if not rut:     errores.append('El RUT es obligatorio.')
        if not nombre:  errores.append('El nombre es obligatorio.')
        if not apellido: errores.append('El apellido es obligatorio.')
        if not password or len(password) < 6:
            errores.append('La contraseña debe tener al menos 6 caracteres.')
        if password != password2:
            errores.append('Las contraseñas no coinciden.')
        if Usuario.objects.filter(rut=rut).exists():
            errores.append('Ya existe un usuario registrado con ese RUT.')

        empresa = None
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id, estado='aprobada')
            except Empresa.DoesNotExist:
                errores.append('La empresa seleccionada no es válida.')

        if errores:
            return render(request, self.template_name, {
                'errores': errores, 'form_data': request.POST, 'empresas': empresas,
            })

        Usuario.objects.create_user(
            rut=rut, password=password,
            nombre=nombre, apellido=apellido,
            email=email, telefono=telefono,
            edad=int(edad) if edad and edad.isdigit() else None,
            genero=genero,
            rol='recolector',
            estado='pendiente',
            empresa=empresa,
        )

        return render(request, self.template_name, {'success': True, 'empresas': empresas})


# ─── GESTIÓN DE ACCESOS (admin Redimir) ───────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class GestionAccesosView(View):
    template_name = 'admin/gestion_accesos.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')

        return render(request, self.template_name, {
            'usuarios_pendientes': Usuario.objects.filter(estado='pendiente').select_related('empresa'),
            'empresas_pendientes': Empresa.objects.filter(estado='pendiente'),
            'todos_usuarios':      Usuario.objects.exclude(rol='admin').select_related('empresa').order_by('-fecha_registro'),
            'todas_empresas':      Empresa.objects.all().order_by('-fecha_registro'),
            'roles':               [('recolector', 'Recolector'), ('empresa', 'Contacto Empresa'), ('admin', 'Admin Redimir')],
        })

    def post(self, request):
        if not _es_admin(request.user):
            return redirect('dashboard')

        accion    = request.POST.get('accion')
        tipo      = request.POST.get('tipo')
        objeto_id = request.POST.get('id')
        rol_asignado = request.POST.get('rol_asignado', '')

        if tipo == 'usuario':
            obj = get_object_or_404(Usuario, id=objeto_id)
            if accion == 'aprobar':
                obj.estado = 'aprobado'
                # Override rol if provided
                if rol_asignado in dict(Usuario.ROLES):
                    obj.rol = rol_asignado
                obj.save()
                messages.success(request, f'Usuario {obj.nombre_completo} aprobado como {obj.get_rol_display()}.')
            elif accion == 'rechazar':
                obj.estado = 'rechazado'
                obj.save()
                messages.warning(request, f'Usuario {obj.nombre_completo} rechazado.')
            elif accion == 'cambiar_rol':
                if rol_asignado in dict(Usuario.ROLES):
                    obj.rol = rol_asignado
                    obj.save()
                    messages.success(request, f'Rol de {obj.nombre_completo} cambiado a {obj.get_rol_display()}.')

        elif tipo == 'empresa':
            obj = get_object_or_404(Empresa, id=objeto_id)
            if accion == 'aprobar':
                obj.estado = 'aprobada'
                obj.fecha_aprobacion = timezone.now()
                obj.save()
                # Also approve the empresa's contact user
                Usuario.objects.filter(empresa=obj, rol='empresa', estado='pendiente').update(estado='aprobado')
                messages.success(request, f'Empresa {obj.nombre} aprobada.')
            elif accion == 'rechazar':
                obj.estado = 'rechazada'
                obj.save()
                messages.warning(request, f'Empresa {obj.nombre} rechazada.')

        return redirect('gestion-accesos')


# ─── FICHA DE TRABAJADOR (admin Redimir) ──────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class BuscarTrabajadorView(View):
    template_name = 'admin/buscar_trabajador.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')

        q = request.GET.get('q', '').strip()
        empresa_id = request.GET.get('empresa', '')
        rol_filtro = request.GET.get('rol', '')

        trabajadores = Usuario.objects.exclude(rol='admin').select_related('empresa')

        if q:
            trabajadores = trabajadores.filter(
                Q(nombre__icontains=q) | Q(apellido__icontains=q) | Q(rut__icontains=q) | Q(email__icontains=q)
            )
        if empresa_id:
            trabajadores = trabajadores.filter(empresa_id=empresa_id)
        if rol_filtro:
            trabajadores = trabajadores.filter(rol=rol_filtro)

        trabajadores = trabajadores.order_by('nombre', 'apellido')

        return render(request, self.template_name, {
            'trabajadores': trabajadores,
            'q': q,
            'empresas': Empresa.objects.filter(activa=True).order_by('nombre'),
            'empresa_sel': empresa_id,
            'rol_sel': rol_filtro,
            'total': trabajadores.count(),
        })


@method_decorator(login_required, name='dispatch')
class FichaTrabajadorView(View):
    template_name = 'admin/ficha_trabajador.html'

    def get(self, request, pk):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')

        from apps.lotes.models import Lote

        trabajador = get_object_or_404(Usuario, pk=pk)
        hace_30    = timezone.now() - timedelta(days=30)

        lotes_todos = Lote.objects.filter(operador=trabajador).select_related('empresa_origen').order_by('-fecha_creacion')
        lotes_mes   = lotes_todos.filter(fecha_creacion__gte=hace_30)

        total_kg_mes   = lotes_mes.aggregate(Sum('cantidad_kg'))['cantidad_kg__sum'] or 0
        total_rec_mes  = lotes_mes.count()
        total_kg_total = lotes_todos.aggregate(Sum('cantidad_kg'))['cantidad_kg__sum'] or 0

        tipos_mes = (
            lotes_mes.values('tipo_residuo')
            .annotate(total=Sum('cantidad_kg'))
            .order_by('-total')
        )
        tipos_labels = [t['tipo_residuo'].capitalize() for t in tipos_mes]
        tipos_values = [float(t['total']) for t in tipos_mes]

        trend_labels, trend_values = [], []
        for i in range(6, -1, -1):
            dia = timezone.now().date() - timedelta(days=i)
            kg  = lotes_todos.filter(fecha_creacion__date=dia).aggregate(Sum('cantidad_kg'))['cantidad_kg__sum'] or 0
            trend_labels.append(dia.strftime('%d/%m'))
            trend_values.append(float(kg))

        return render(request, self.template_name, {
            'trabajador':    trabajador,
            'lotes':         lotes_todos[:30],
            'total_kg_mes':  float(total_kg_mes),
            'total_rec_mes': total_rec_mes,
            'total_kg_total': float(total_kg_total),
            'total_rec_total': lotes_todos.count(),
            'tipos_labels':  tipos_labels,
            'tipos_values':  tipos_values,
            'trend_labels':  trend_labels,
            'trend_values':  trend_values,
            'roles':         Usuario.ROLES,
        })

    def post(self, request, pk):
        """Change role, estado, block or delete directly from ficha."""
        if not _es_admin(request.user):
            return redirect('dashboard')
            
        trabajador = get_object_or_404(Usuario, pk=pk)
        accion = request.POST.get('accion', 'guardar')
        
        if accion == 'eliminar':
            nombre = trabajador.nombre_completo
            trabajador.delete()
            messages.success(request, f'La cuenta de {nombre} fue eliminada permanentemente del sistema.')
            return redirect('buscar-trabajador')
            
        elif accion == 'bloquear':
            trabajador.is_active = False
            trabajador.estado = 'rechazado'
            trabajador.save()
            messages.warning(request, f'La cuenta de {trabajador.nombre_completo} ha sido bloqueada/desactivada.')
            
        elif accion == 'desbloquear':
            trabajador.is_active = True
            trabajador.estado = 'aprobado'
            trabajador.save()
            messages.success(request, f'La cuenta de {trabajador.nombre_completo} ha sido reactivada.')
            
        else: # Guardar cambios form
            nuevo_rol  = request.POST.get('rol')
            nuevo_estado = request.POST.get('estado')
            if nuevo_rol in dict(Usuario.ROLES):
                trabajador.rol = nuevo_rol
            if nuevo_estado in dict(Usuario.ESTADOS):
                trabajador.estado = nuevo_estado
                if nuevo_estado == 'aprobado':
                    trabajador.is_active = True
                elif nuevo_estado == 'rechazado':
                    trabajador.is_active = False
            trabajador.save()
            messages.success(request, f'Accesos de {trabajador.nombre_completo} guardados correctamente.')
            
        return redirect('ficha-trabajador', pk=pk)


class AuditLogsView(View):
    """
    Vista de historial de auditoría de cambios para Gerencia y Administradores.
    Puntos 1 y 14 del Checklist Maestro Redimir.
    """
    template_name = 'admin/audit_logs.html'

    def get(self, request):
        if not (request.user.rol in ('admin', 'gerencia') or request.user.is_staff):
            messages.error(request, 'Acceso denegado.')
            return redirect('dashboard')
        
        from .models import AuditLog
        logs = AuditLog.objects.all().select_related('usuario')[:200]
        return render(request, self.template_name, {'logs': logs})


# ─── Crear Recolector (Admin directo) ────────────────────────────────────────

@method_decorator(login_required, name='dispatch')
class RecolectorCrearAdminView(View):
    """Vista de creación rápida de recolector/operador para administradores."""
    template_name = 'admin/crear_recolector_admin.html'

    def get(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')
        empresas = Empresa.objects.filter(activa=True).order_by('nombre')
        return render(request, self.template_name, {'empresas': empresas, 'roles': Usuario.ROLES})

    def post(self, request):
        if not _es_admin(request.user):
            messages.error(request, 'No tienes permiso.')
            return redirect('dashboard')

        empresas = Empresa.objects.filter(activa=True).order_by('nombre')
        rut      = request.POST.get('rut', '').strip().upper()
        nombre   = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        email    = request.POST.get('email', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        edad     = request.POST.get('edad', None)
        genero   = request.POST.get('genero', '')
        empresa_id = request.POST.get('empresa', None)
        password   = request.POST.get('password', '')
        password2  = request.POST.get('password2', '')
        rol        = request.POST.get('rol', 'recolector')
        estado_val = request.POST.get('estado', 'aprobado')

        errores = []
        if not rut:      errores.append('El RUT es obligatorio.')
        if not nombre:   errores.append('El nombre es obligatorio.')
        if not apellido: errores.append('El apellido es obligatorio.')
        if not password or len(password) < 6:
            errores.append('La contraseña debe tener al menos 6 caracteres.')
        if password != password2:
            errores.append('Las contraseñas no coinciden.')
        if Usuario.objects.filter(rut=rut).exists():
            errores.append('Ya existe un usuario registrado con ese RUT.')

        empresa = None
        if empresa_id:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
            except Empresa.DoesNotExist:
                errores.append('La empresa seleccionada no es válida.')

        if errores:
            return render(request, self.template_name, {
                'errores': errores, 'form_data': request.POST,
                'empresas': empresas, 'roles': Usuario.ROLES,
            })

        usuario = Usuario.objects.create_user(
            rut=rut, password=password,
            nombre=nombre, apellido=apellido,
            email=email, telefono=telefono,
            edad=int(edad) if edad and edad.isdigit() else None,
            genero=genero,
            rol=rol,
            estado=estado_val,
            empresa=empresa,
        )

        from .models import AuditLog
        AuditLog.registrar(
            usuario=request.user,
            accion='creacion',
            modelo='Usuario',
            registro_id=usuario.pk,
            detalles=f"Usuario '{usuario.nombre_completo}' ({rol}) creado directamente por admin.",
            ip=request.META.get('REMOTE_ADDR')
        )

        messages.success(request, f'Usuario "{usuario.nombre_completo}" creado exitosamente.')
        return redirect('buscar-trabajador')


