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

    def contactos_para(self, tipo):
        """Retorna queryset de ContactoEmpresa que reciben el tipo indicado."""
        return self.contactos.filter(**{f'recibe_{tipo}': True}, activo=True)

    def emails_para(self, tipo):
        """Lista de emails de contactos activos que reciben el tipo indicado."""
        return list(self.contactos.filter(**{f'recibe_{tipo}': True}, activo=True).values_list('email', flat=True))


class ContactoEmpresa(models.Model):
    """
    Contactos adicionales segmentados por empresa.
    Permite enviar diferentes certificados/notificaciones a distintas personas.
    """
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='contactos')
    nombre  = models.CharField(max_length=100, verbose_name='Nombre Completo')
    cargo   = models.CharField(max_length=80, blank=True, verbose_name='Cargo / Área')
    email   = models.EmailField(verbose_name='Correo Electrónico')
    telefono = models.CharField(max_length=20, blank=True)

    # Tipos de documentos/notificaciones que recibe este contacto
    recibe_certificados  = models.BooleanField(default=False, verbose_name='Recibe Certificados de Trazabilidad')
    recibe_estados_pago  = models.BooleanField(default=False, verbose_name='Recibe Estados de Pago')
    recibe_reportes      = models.BooleanField(default=False, verbose_name='Recibe Reportes Operacionales')
    recibe_notificaciones= models.BooleanField(default=True,  verbose_name='Recibe Notificaciones Generales')

    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'contactos_empresa'
        ordering = ['nombre']
        verbose_name = 'Contacto de Empresa'
        verbose_name_plural = 'Contactos de Empresa'

    def __str__(self):
        return f"{self.nombre} <{self.email}> — {self.empresa.nombre}"

    def tipos_asignados(self):
        tipos = []
        if self.recibe_certificados:   tipos.append('Certificados')
        if self.recibe_estados_pago:   tipos.append('Estados de Pago')
        if self.recibe_reportes:       tipos.append('Reportes')
        if self.recibe_notificaciones: tipos.append('Notificaciones')
        return tipos




class SolicitudRecoleccion(models.Model):
    MODULOS = [
        ('rsd',         'RSD / Basura'),
        ('escombros',   'Escombros / RESCON'),
        ('reciclables', 'Reciclables / Eco-equivalencia'),
        ('otros',       'Otros / Servicio Personalizado'),
    ]

    MATERIALES = [
        ('carton',      'Cartón / Papel'),
        ('pet',         'Botellas PET'),
        ('vidrio',      'Vidrio'),
        ('latas',       'Latas de Aluminio'),
        ('film',        'Film LDPE'),
        ('plastico',    'Plástico General'),
        ('escombros',   'Escombros / RESCON'),
        ('rsd',         'RSD / Basura General'),
        ('mixto',       'Mixto / Varios'),
        ('otros',       'Otro Material / Servicio Especial'),
    ]

    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('asignada', 'Asignada a Operador'),
        ('completada', 'Completada'),
        ('cancelada', 'Cancelada'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE,
                                related_name='solicitudes')
    modulo = models.CharField(max_length=20, choices=MODULOS, default='reciclables')
    tipo_material = models.CharField(max_length=50, choices=MATERIALES, default='carton')
    cantidad_estimada = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidad_medida = models.CharField(max_length=30, default='kg')
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_estimado = models.DecimalField(max_digits=14, decimal_places=2, default=0)

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
    Estado de Pago Interno Único por Empresa para consolidar cobros y valorización comercial.
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
    empresa         = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name='estado_de_pago', verbose_name='Empresa Solicitante')
    orden_compra    = models.CharField(max_length=100, blank=True, null=True, verbose_name='N° Orden de Compra')
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
        ('rsd', 'RSD / Basura'),
        ('escombros', 'RESCON / Escombros'),
        ('reciclables', 'Reciclables / Eco-equivalencia'),
        ('otros', 'Otros / Servicio Personalizado'),
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


def actualizar_o_crear_edp_empresa(empresa, periodo_inicio=None, periodo_fin=None, usuario=None):
    """
    Función centralizada para calcular y actualizar automáticamente el Estado de Pago Único de una Empresa.
    Se coordina automáticamente con el tarifario de la empresa y los servicios/solicitudes registrados.
    """
    from decimal import Decimal
    from django.utils import timezone
    from django.db.models import Q
    from apps.servicios.models import Servicio
    
    today = timezone.now().date()
    p_inicio = periodo_inicio or today.replace(day=1)
    p_fin = periodo_fin or today

    # Buscar o crear el EDP único de la empresa
    edp = EstadoDePago.objects.filter(empresa=empresa).first()
    if not edp:
        year = today.strftime("%Y")
        count = EstadoDePago.objects.filter(fecha_creacion__year=today.year).count() + 1
        edp = EstadoDePago.objects.create(
            empresa=empresa,
            numero_edp=f"EDP-{year}-{count:04d}",
            periodo_inicio=p_inicio,
            periodo_fin=p_fin,
            creado_por=usuario,
            estado='borrador',
            observaciones=f'Estado de Pago Automático generado/actualizado el {today.strftime("%d/%m/%Y")}'
        )

    # Limpiar detalles anteriores para recalcular con tarifario vigente
    edp.detalles.all().delete()

    TARIFA_RETIRO_PREDETERMINADA = Decimal('150000')

    total_calculado = Decimal('0')
    count_servicios = 0

    # 1. Procesar Servicios de Retiro de la Empresa
    servicios_qs = Servicio.objects.filter(empresa=empresa, is_active=True).distinct()
    for s in servicios_qs:
        cant = Decimal('1')
        unid = 'servicio'
        desc = f"Retiro {s.get_modulo_display()} — Servicio #{s.id}"

        tarifa_custom = TarifaEmpresa.objects.filter(empresa=empresa, modulo=s.modulo).first()
        if not tarifa_custom:
            tarifa_custom = TarifaEmpresa.objects.filter(empresa=empresa).first()

        tarifa = tarifa_custom.precio_unitario if tarifa_custom else TARIFA_RETIRO_PREDETERMINADA
        sub_item = cant * tarifa
        total_calculado += sub_item
        count_servicios += 1

        DetalleEstadoDePago.objects.create(
            estado_de_pago=edp,
            servicio=s,
            fecha_servicio=s.fecha_retiro_real.date() if s.fecha_retiro_real else s.fecha_solicitud.date(),
            modulo=s.get_modulo_display(),
            descripcion=desc,
            cantidad=cant,
            unidad_medida=unid,
            tarifa_unitaria=tarifa,
            subtotal=sub_item
        )

    # 2. Procesar Solicitudes de Recolección de la Empresa
    solicitudes_qs = SolicitudRecoleccion.objects.filter(empresa=empresa).exclude(estado='cancelada')
    for sol in solicitudes_qs:
        cant = Decimal('1')
        unid = 'servicio'
        mat_display = sol.get_tipo_material_display() if hasattr(sol, 'get_tipo_material_display') else sol.modulo.upper()
        desc = f"Solicitud Recolección ({mat_display}) — Solicitud #{sol.id}"

        tarifa_custom = TarifaEmpresa.objects.filter(empresa=empresa, modulo=sol.modulo).first()
        if not tarifa_custom:
            tarifa_custom = TarifaEmpresa.objects.filter(empresa=empresa).first()

        tarifa = tarifa_custom.precio_unitario if tarifa_custom else TARIFA_RETIRO_PREDETERMINADA
        sub_item = cant * tarifa
        total_calculado += sub_item
        count_servicios += 1

        DetalleEstadoDePago.objects.create(
            estado_de_pago=edp,
            servicio=None,
            fecha_servicio=sol.fecha_solicitada.date() if sol.fecha_solicitada else today,
            modulo=sol.get_modulo_display() if hasattr(sol, 'get_modulo_display') else sol.modulo.upper(),
            descripcion=desc,
            cantidad=cant,
            unidad_medida=unid,
            tarifa_unitaria=tarifa,
            subtotal=sub_item
        )

    edp.total_servicios = count_servicios
    edp.subtotal_neto = total_calculado
    edp.iva = round(total_calculado * Decimal('0.19'), 2)
    edp.total_bruto = edp.subtotal_neto + edp.iva
    edp.save()
    return edp




