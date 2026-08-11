from django.db import models
from django.utils import timezone


class Empresa(models.Model):
    RUBROS = [
        ('manufactura', 'Manufactura'),
        ('construccion', 'Construcción'),
        ('retail', 'Retail / Comercio'),
        ('alimentacion', 'Alimentación'),
        ('logistica', 'Logística / Transporte'),
        ('mineria', 'Minería'),
        ('servicios', 'Servicios'),
        ('educacion', 'Educación'),
        ('salud', 'Salud'),
        ('otro', 'Otro'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente de Aprobación'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
        ('suspendida', 'Suspendida'),
    ]

    nombre = models.CharField(max_length=150, verbose_name='Razón Social')
    rut = models.CharField(max_length=12, unique=True, verbose_name='RUT Empresa')
    email_contacto = models.EmailField(verbose_name='Email de Contacto')
    telefono = models.CharField(max_length=15, blank=True)
    direccion = models.CharField(max_length=200, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    rubro = models.CharField(max_length=30, choices=RUBROS, default='otro')
    giro = models.CharField(max_length=150, blank=True, verbose_name='Giro Comercial')

    nombre_contacto = models.CharField(max_length=100, blank=True, verbose_name='Nombre de Contacto')
    cargo_contacto = models.CharField(max_length=80, blank=True, verbose_name='Cargo')

    logo = models.ImageField(upload_to='logos/empresas/', null=True, blank=True)

    activa = models.BooleanField(default=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'empresas'
        ordering = ['nombre']
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return f"{self.nombre} ({self.rut})"

    def total_trabajadores_activos(self):
        return self.trabajadores.filter(is_active=True, estado='aprobado').count()

    def total_recolecciones_mes(self):
        hace_30 = timezone.now() - timezone.timedelta(days=30)
        return self.lotes.filter(fecha_creacion__gte=hace_30).count()

    def total_kg_mes(self):
        from django.db.models import Sum
        hace_30 = timezone.now() - timezone.timedelta(days=30)
        result = self.lotes.filter(fecha_creacion__gte=hace_30).aggregate(Sum('cantidad_kg'))
        return result['cantidad_kg__sum'] or 0


class SolicitudRecoleccion(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('asignada', 'Asignada a Operador'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,
                                related_name='solicitudes')
    descripcion = models.TextField()
    direccion_recoleccion = models.CharField(max_length=255)
    fecha_solicitada = models.DateTimeField()
    observaciones = models.TextField(blank=True)

    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    operador_asignado = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='solicitudes_asignadas'
    )

    creado_por = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='solicitudes_creadas'
    )

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'solicitudes_recoleccion'
        ordering = ['-fecha_creacion']
        verbose_name = 'Solicitud de Recolección'
        verbose_name_plural = 'Solicitudes de Recolección'

    def __str__(self):
        return f"Solicitud #{self.pk} - {self.empresa.nombre} ({self.get_estado_display()})"


class EstadoDePago(models.Model):
    """
    Estado de Pago Interno para consolidar cobros y valorización comercial por cliente y período.
    Punto 16 del Checklist Maestro Redimir.
    Valores comerciales restringidos únicamente a Gerencia / Admin.
    """
    ESTADOS = [
        ('borrador',   'Borrador Interno'),
        ('emitido',    'Emitido'),
        ('pagado',     'Pagado'),
        ('anulado',    'Anulado'),
    ]

    numero_edp      = models.CharField(max_length=50, unique=True, verbose_name='N° Estado de Pago')
    empresa         = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='estados_de_pago')
    periodo_inicio  = models.DateField()
    periodo_fin     = models.DateField()
    fecha_emision   = models.DateField(default=timezone.now)
    
    # Detalle cuantitativo
    total_servicios = models.IntegerField(default=0)
    subtotal_neto   = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Subtotal Neto ($)')
    iva             = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='IVA 19% ($)')
    total_bruto     = models.DecimalField(max_digits=14, decimal_places=2, default=0, verbose_name='Total Bruto ($)')
    
    estado          = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    observaciones   = models.TextField(blank=True)
    
    creado_por      = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, related_name='edps_creados')
    fecha_creacion  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'estados_de_pago'
        ordering = ['-fecha_creacion']
        verbose_name = 'Estado de Pago Interno'
        verbose_name_plural = 'Estados de Pago Internos'

    def __str__(self):
        return f"EDP {self.numero_edp} — {self.empresa.nombre} (${self.total_bruto:,.0f})"

    def save(self, *args, **kwargs):
        if not self.numero_edp:
            year = timezone.now().strftime("%Y")
            count = EstadoDePago.objects.filter(fecha_creacion__year=timezone.now().year).count() + 1
            self.numero_edp = f"EDP-{year}-{count:04d}"
        super().save(*args, **kwargs)


class DetalleEstadoDePago(models.Model):
    """
    Línea de detalle desglosada por servicio prestado en un Estado de Pago Interno.
    """
    estado_de_pago   = models.ForeignKey(EstadoDePago, on_delete=models.CASCADE, related_name='detalles')
    servicio         = models.ForeignKey('servicios.Servicio', on_delete=models.SET_NULL, null=True, blank=True)
    fecha_servicio   = models.DateField(null=True, blank=True)
    modulo           = models.CharField(max_length=30, blank=True)
    descripcion      = models.CharField(max_length=255)
    cantidad         = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unidad_medida    = models.CharField(max_length=30, default='servicio')
    tarifa_unitaria  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    subtotal         = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'detalles_estado_de_pago'
        verbose_name = 'Detalle de Estado de Pago'
        verbose_name_plural = 'Detalles de Estado de Pago'

    def __str__(self):
        return f"{self.estado_de_pago.numero_edp} — {self.descripcion} (${self.subtotal:,.0f})"


class TarifaEmpresa(models.Model):
    """
    Tarifario comercial configurado por empresa cliente y tipo de residuo/reciclaje.
    Utilizado para valorizar automáticamente los retiros en el Estado de Pago (EDP).
    """
    MODULOS = [
        ('rsd', 'RSD'),
        ('escombros', 'RESCON / Escombros'),
        ('reciclables', 'Reciclables'),
    ]

    empresa         = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='tarifas')
    modulo          = models.CharField(max_length=30, choices=MODULOS, default='reciclables')
    tipo_material   = models.CharField(max_length=50, help_text="ej: pet, carton, vidrio, latas, rsd, escombros")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Precio Unitario ($)')
    unidad_medida   = models.CharField(max_length=20, default='kg')
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'tarifas_empresa'
        unique_together = ('empresa', 'modulo', 'tipo_material')
        verbose_name = 'Tarifa Comercial Empresa'
        verbose_name_plural = 'Tarifas Comerciales Empresa'

    def __str__(self):
        return f"{self.empresa.nombre} — {self.tipo_material.upper()} (${self.precio_unitario:,.0f}/{self.unidad_medida})"



