from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone


class UsuarioManager(BaseUserManager):
    def create_user(self, rut, password=None, **extra_fields):
        if not rut:
            raise ValueError('El RUT es obligatorio.')
        rut = rut.strip().upper()
        user = self.model(rut=rut, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, rut, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('rol', 'admin')
        extra_fields.setdefault('estado', 'aprobado')
        return self.create_user(rut, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    ROLES = [
        ('gerencia',   'Gerencia / Superadmin'),
        ('admin',      'Administrador Redimir'),
        ('recolector', 'Recolector / Operador'),
        ('empresa',    'Contacto de Empresa'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente de Aprobación'),
        ('aprobado',  'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    GENEROS = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
        ('O', 'Otro'),
    ]

    rut       = models.CharField(max_length=12, unique=True, verbose_name='RUT')
    nombre    = models.CharField(max_length=80)
    apellido  = models.CharField(max_length=80)
    email     = models.EmailField(blank=True)
    telefono  = models.CharField(max_length=15, blank=True)
    edad      = models.PositiveSmallIntegerField(null=True, blank=True)
    genero    = models.CharField(max_length=1, choices=GENEROS, blank=True)
    avatar    = models.ImageField(upload_to='avatares/', null=True, blank=True)

    rol    = models.CharField(max_length=20, choices=ROLES, default='recolector')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')

    empresa = models.ForeignKey(
        'empresas.Empresa', on_delete=models.CASCADE,
        null=True, blank=True, related_name='trabajadores'
    )

    is_active = models.BooleanField(default=True)
    is_staff  = models.BooleanField(default=False)
    fecha_registro       = models.DateTimeField(auto_now_add=True)
    ultimo_login_custom  = models.DateTimeField(null=True, blank=True)

    objects = UsuarioManager()

    USERNAME_FIELD  = 'rut'
    REQUIRED_FIELDS = ['nombre', 'apellido']

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.rut}) — {self.get_rol_display()}"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    @property
    def esta_aprobado(self):
        return self.estado == 'aprobado'

    # ── helpers ──────────────────────────────────────────────
    def es_gerencia(self):
        return self.rol == 'gerencia' or self.is_superuser

    def es_admin(self):
        return self.rol in ('admin', 'gerencia') or self.is_staff

    def es_recolector(self):
        return self.rol == 'recolector'

    def es_empresa(self):
        return self.rol == 'empresa'

    # backward-compat alias used by old templates
    def es_operador(self):
        return self.rol in ('recolector', 'operador')


class AuditLog(models.Model):
    """
    Registro centralizado de auditoría de cambios y trazabilidad de acciones.
    Punto 1 y 14 del Checklist Maestro Redimir.
    """
    ACCIONES = [
        ('creacion',     'Creación'),
        ('modificacion', 'Modificación'),
        ('eliminacion',  'Desactivación / Eliminación Lógica'),
        ('validacion',   'Validación de Servicio'),
        ('emision_doc',  'Emisión de Documento'),
        ('login',        'Inicio de Sesión'),
        ('configuracion','Cambio de Configuración'),
    ]

    usuario          = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='logs_auditoria')
    accion           = models.CharField(max_length=30, choices=ACCIONES)
    modelo           = models.CharField(max_length=80, verbose_name='Modelo Afectado')
    registro_id      = models.CharField(max_length=50, blank=True, verbose_name='ID / Folio Registro')
    campo_modificado = models.CharField(max_length=100, blank=True, verbose_name='Campo Modificado')
    valor_anterior   = models.TextField(blank=True, verbose_name='Valor Anterior')
    valor_nuevo      = models.TextField(blank=True, verbose_name='Valor Nuevo')
    detalles         = models.TextField(verbose_name='Detalles / Cambios Realizados')
    ip_origen        = models.GenericIPAddressField(null=True, blank=True)
    fecha_registro   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'audit_logs'
        ordering = ['-fecha_registro']
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'

    def __str__(self):
        usr = self.usuario.nombre_completo if self.usuario else "Sistema"
        return f"[{self.fecha_registro.strftime('%d/%m/%Y %H:%M')}] {usr} — {self.get_accion_display()} en {self.modelo} (#{self.registro_id})"

    @classmethod
    def registrar(cls, usuario, accion, modelo, registro_id="", detalles="", campo="", valor_anterior="", valor_nuevo="", ip=None):
        return cls.objects.create(
            usuario=usuario,
            accion=accion,
            modelo=modelo,
            registro_id=str(registro_id),
            campo_modificado=campo,
            valor_anterior=str(valor_anterior) if valor_anterior is not None else "",
            valor_nuevo=str(valor_nuevo) if valor_nuevo is not None else "",
            detalles=detalles,
            ip_origen=ip
        )

