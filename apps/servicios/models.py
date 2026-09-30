"""
MODELOS DE SERVICIOS - REDIMIR
Módulos: RSD/Basura, Escombros/RESCON, Reciclables/Eco-equivalencia
"""
from django.db import models
from django.utils import timezone
from django.db.models import Sum


# ─── MODELO BASE DE SERVICIO ─────────────────────────────────────────────────

class Servicio(models.Model):
    """
    Representa una solicitud/servicio de retiro de residuos.
    Flujo de estados:
      solicitado → programado → asignado → en_ruta → retirado
      → pendiente_validacion → observado → validado → documento_emitido → cerrado
    """
    MODULOS = [
        ('rsd',         'RSD / Basura'),
        ('escombros',   'Escombros / RESCON'),
        ('reciclables', 'Reciclables / Eco-equivalencia'),
    ]
    ESTADOS = [
        ('solicitado',            'Solicitado'),
        ('programado',            'Programado'),
        ('asignado',              'Asignado'),
        ('en_ruta',               'En Ruta'),
        ('retirado',              'Retirado'),
        ('pendiente_validacion',  'Pendiente de Validación'),
        ('observado',             'Observado'),
        ('validado',              'Validado'),
        ('documento_emitido',     'Documento Emitido'),
        ('cerrado',               'Cerrado'),
        ('cancelado',             'Cancelado'),
    ]

    empresa  = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='servicios')
    modulo   = models.CharField(max_length=20, choices=MODULOS)
    estado   = models.CharField(max_length=30, choices=ESTADOS, default='solicitado')

    # Fechas
    fecha_solicitud   = models.DateTimeField(auto_now_add=True)
    fecha_programada  = models.DateTimeField(null=True, blank=True)
    ventana_inicio    = models.TimeField(null=True, blank=True, verbose_name='Hour desde')
    ventana_fin       = models.TimeField(null=True, blank=True, verbose_name='Hora hasta')
    fecha_retiro_real = models.DateTimeField(null=True, blank=True)

    # Datos de solicitud
    direccion            = models.CharField(max_length=255, verbose_name='Dirección de Retiro')
    planta_destino       = models.CharField(max_length=200, blank=True, verbose_name='Planta / Destino Receptor')
    contacto_responsable = models.CharField(max_length=100, blank=True)
    telefono_contacto      = models.CharField(max_length=20, blank=True)
    cantidad_estimada      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    unidad_estimada        = models.CharField(max_length=30, blank=True, default='kg')
    observaciones          = models.TextField(blank=True)

    # Personal
    operador         = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL,
                                         null=True, blank=True, related_name='servicios_asignados')
    usuario_creador  = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL,
                                         null=True, related_name='servicios_creados')

    # Auditoría de validación / documentos
    usuario_validador    = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name='validaciones')
    fecha_validacion     = models.DateTimeField(null=True, blank=True)
    observacion_admin    = models.TextField(blank=True, verbose_name='Observación del administrador')

    usuario_emisor_doc   = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name='documentos_emitidos')
    fecha_emision_doc    = models.DateTimeField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'servicios'
        ordering = ['-fecha_solicitud']
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'

    def __str__(self):
        return f"#{self.pk} — {self.empresa.nombre} [{self.get_modulo_display()}] — {self.get_estado_display()}"

    @property
    def es_pendiente_validacion(self):
        return self.estado == 'pendiente_validacion'

    @property
    def numero_folio(self):
        """Formato: SRV-2026-0001"""
        return f"SRV-{self.fecha_solicitud.year}-{self.pk:04d}"

    def get_registro(self):
        """Devuelve el registro del módulo correspondiente."""
        if self.modulo == 'rsd':
            return self.registro_rsd_set.first()
        elif self.modulo == 'escombros':
            return self.registro_escombros_set.first()
        elif self.modulo == 'reciclables':
            return self.registro_reciclables_set.first()
        return None


# ─── MÓDULO 1: RSD / BASURA ──────────────────────────────────────────────────

class RegistroRSD(models.Model):
    """Registro de retiro de Residuos Sólidos Domiciliarios."""
    TIPOS_RESIDUO = [
        ('rsd',             'RSD / Basura Domiciliaria'),
        ('basura_general',  'Basura General'),
        ('rechazo',         'Rechazo / No-reciclable'),
        ('organico',        'Orgánico'),
        ('mixto',           'Mixto'),
    ]
    DESTINOS = [
        ('socsal',           'SOCSAL - Relleno Sanitario'),
        ('relleno_regional', 'Relleno Sanitario Regional'),
        ('municipalidad',    'Municipalidad'),
        ('otro',             'Otro Receptor Autorizado'),
    ]

    servicio        = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='registro_rsd_set')
    tipo_residuo    = models.CharField(max_length=30, choices=TIPOS_RESIDUO, default='rsd')
    cantidad_kg     = models.DecimalField(max_digits=10, decimal_places=2)
    ticket_externo  = models.CharField(max_length=100, verbose_name='N° Ticket Externo')
    destino_receptor = models.CharField(max_length=50, choices=DESTINOS, default='socsal')
    destino_otro    = models.CharField(max_length=200, blank=True, verbose_name='Especificar destino')
    observaciones   = models.TextField(blank=True)

    usuario_registro = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True)
    fecha_registro   = models.DateTimeField(auto_now_add=True)
    ubicacion_gps    = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'registros_rsd'
        ordering = ['-fecha_registro']
        verbose_name = 'Registro RSD'

    def __str__(self):
        return f"RSD #{self.pk} — {self.cantidad_kg} kg — Ticket {self.ticket_externo}"


class FotoRegistroRSD(models.Model):
    """Fotos de evidencia del retiro RSD. Mínimo 1 obligatoria."""
    registro   = models.ForeignKey(RegistroRSD, on_delete=models.CASCADE, related_name='fotos')
    foto       = models.ImageField(upload_to='registros/rsd/%Y/%m/%d/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    es_principal = models.BooleanField(default=False)

    class Meta:
        db_table = 'fotos_rsd'
        ordering = ['-es_principal', 'fecha_subida']


# ─── MÓDULO 2: ESCOMBROS / RESCON ────────────────────────────────────────────

class RegistroEscombros(models.Model):
    """Registro de retiro de Escombros / RESCON."""
    TIPOS_RESIDUO = [
        ('escombros',  'Escombros'),
        ('rescon',     'RESCON'),
        ('aridos',     'Áridos'),
        ('tierra',     'Tierra'),
        ('voluminoso', 'Voluminoso'),
        ('mixto',      'Mixto'),
    ]
    UNIDADES = [
        ('kg',      'Kilogramos (kg)'),
        ('m3',      'Metros Cúbicos (m³)'),
        ('sacos',   'Sacos'),
        ('batea',   'Batea'),
        ('camion',  'Camión'),
        ('otro',    'Otro'),
    ]
    DESTINOS = [
        ('municipalidad', 'Municipalidad'),
        ('rescon',        'RESCON Autorizado'),
        ('esavi',         'ESAVI'),
        ('otro',          'Otro Receptor Autorizado'),
    ]

    servicio        = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='registro_escombros_set')
    tipo_residuo    = models.CharField(max_length=30, choices=TIPOS_RESIDUO, default='escombros')
    cantidad        = models.DecimalField(max_digits=10, decimal_places=2)
    unidad          = models.CharField(max_length=20, choices=UNIDADES, default='m3')
    ticket_externo  = models.CharField(max_length=100, verbose_name='N° Ticket Externo')
    destino_receptor = models.CharField(max_length=30, choices=DESTINOS, default='municipalidad')
    destino_otro    = models.CharField(max_length=200, blank=True)
    cert_recepcion  = models.FileField(upload_to='certs_recepcion/%Y/%m/', null=True, blank=True,
                                        verbose_name='Certificado de Recepción (opcional)')
    observaciones   = models.TextField(blank=True)

    usuario_registro = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True)
    fecha_registro   = models.DateTimeField(auto_now_add=True)
    ubicacion_gps    = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'registros_escombros'
        ordering = ['-fecha_registro']
        verbose_name = 'Registro Escombros'

    def __str__(self):
        return f"Escombros #{self.pk} — {self.cantidad} {self.get_unidad_display()} — Ticket {self.ticket_externo}"


class FotoRegistroEscombros(models.Model):
    registro   = models.ForeignKey(RegistroEscombros, on_delete=models.CASCADE, related_name='fotos')
    foto       = models.ImageField(upload_to='registros/escombros/%Y/%m/%d/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    es_principal = models.BooleanField(default=False)

    class Meta:
        db_table = 'fotos_escombros'


# ─── MÓDULO 3: RECICLABLES / ECO-EQUIVALENCIA ────────────────────────────────

class RegistroReciclables(models.Model):
    """Registro de retiro de materiales reciclables con cálculo eco-equivalencia."""
    MATERIALES = [
        ('carton',    'Cartón'),
        ('papel',     'Papel'),
        ('pet',       'Botellas PET (Plástico)'),
        ('latas',     'Latas de Aluminio'),
        ('film',      'Film LDPE'),
        ('carretes',  'Carretes'),
        ('sunchos',   'Sunchos'),
        ('vidrio',    'Vidrio'),
        ('tetrapak',  'Tetrapak'),
        ('plastico',  'Plástico general'),
        ('pallets',   'Pallets'),
        ('otro',      'Otro'),
    ]
    DESTINOS = [
        ('interno',  'Gestión interna Redimir'),
        ('gestor',   'Gestor autorizado'),
        ('receptor', 'Receptor directo'),
    ]

    servicio    = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='registro_reciclables_set')
    material    = models.CharField(max_length=30, choices=MATERIALES)
    cantidad_kg = models.DecimalField(max_digits=10, decimal_places=2)
    unidades    = models.PositiveIntegerField(null=True, blank=True,
                                              verbose_name='Unidades (carretes, sacos, pallets, etc.)')
    destino     = models.CharField(max_length=20, choices=DESTINOS, default='gestor')
    destino_otro = models.CharField(max_length=200, blank=True)
    observaciones = models.TextField(blank=True)

    usuario_registro = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True)
    fecha_registro   = models.DateTimeField(auto_now_add=True)
    ubicacion_gps    = models.CharField(max_length=255, blank=True)

    # Cálculo eco-equivalencia (se calcula al validar)
    eco_agua_L       = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    eco_co2_kg       = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    eco_energia_kwh  = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    eco_petroleo_L   = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    eco_arboles      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'registros_reciclables'
        ordering = ['-fecha_registro']
        verbose_name = 'Registro Reciclable'

    def __str__(self):
        return f"Reciclable #{self.pk} — {self.get_material_display()} {self.cantidad_kg} kg"

    def calcular_eco_equivalencia(self):
        """Calcula eco-equivalencia usando FactorEcoEquivalencia."""
        from apps.calculadora.models import FactorEcoEquivalencia
        factor = FactorEcoEquivalencia.get_factor_activo(self.material)
        if not factor:
            return
        kg = float(self.cantidad_kg)
        self.eco_agua_L      = round(kg * float(factor.factor_agua_lxkg), 2)
        self.eco_co2_kg      = round(kg * float(factor.factor_co2_kgxkg), 2)
        self.eco_energia_kwh = round(kg * float(factor.factor_energia_kwhxkg), 2)
        self.eco_petroleo_L  = round(kg * float(factor.factor_petroleo_lxkg), 2)
        self.eco_arboles     = round(kg * float(factor.factor_arboles_kgxkg), 4)
        self.save(update_fields=['eco_agua_L','eco_co2_kg','eco_energia_kwh','eco_petroleo_L','eco_arboles'])


class FotoRegistroReciclables(models.Model):
    registro   = models.ForeignKey(RegistroReciclables, on_delete=models.CASCADE, related_name='fotos')
    foto       = models.ImageField(upload_to='registros/reciclables/%Y/%m/%d/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    es_principal = models.BooleanField(default=False)

    class Meta:
        db_table = 'fotos_reciclables'


# ══════════════════════════════════════════════════════════════════════════════
# MÓDULO REDIMIR — RETIROS RELACIONALES, TICKETS DE BÁSCULA E INFORMES
# ══════════════════════════════════════════════════════════════════════════════

class CatalogoMaterialRetiro(models.Model):
    CATEGORIAS = [
        ('Reciclaje', 'Reciclaje (Papel, Cartón, Plástico, etc.)'),
        ('Madera', 'Madera y Derivados (Pallets, Carretes)'),
        ('Envases', 'Envases y Contenedores (Tambores, Bidones)'),
        ('Metales', 'Metales y Chatarra (Aluminio, Zuncho, etc.)'),
        ('Domestico', 'Residuos Domésticos / Basura'),
        ('Peligroso', 'Residuos Peligrosos (RESPEL)'),
        ('Otro', 'Otros Residuos'),
    ]

    UNIDADES_MEDIDA = [
        ('kg', 'Solo Kilogramos (kg)'),
        ('un', 'Solo Unidades (un)'),
        ('kg_un', 'Kilogramos y Unidades (kg + un)'),
    ]

    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre del Material")
    codigo = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código / Abreviación")
    categoria = models.CharField(max_length=50, choices=CATEGORIAS, default='Reciclaje', verbose_name="Categoría")
    unidad_medida = models.CharField(max_length=20, choices=UNIDADES_MEDIDA, default='kg', verbose_name="Unidad de Medida")
    peso_unitario_kg = models.DecimalField(
        max_digits=8, decimal_places=2, default=0.00,
        verbose_name="Factor conversión a kg (kg por unidad)",
        help_text="Ej: 20 kg por palet, 5.5 kg por carrete de madera, 10 kg por tambor, 1 kg por bidón 20L"
    )
    orden = models.IntegerField(default=0, verbose_name="Orden de visualización")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return self.nombre

    class Meta:
        db_table = 'catalogos_material_retiro'
        verbose_name = "Catálogo Material Retiro"
        verbose_name_plural = "Catálogo Materiales Retiro"
        ordering = ['orden', 'nombre']


class TicketRetiro(models.Model):
    empresa = models.ForeignKey(
        'empresas.Empresa', on_delete=models.CASCADE,
        related_name='tickets_retiro', verbose_name="Empresa / Cliente"
    )
    servicio = models.ForeignKey(
        Servicio, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tickets_pesaje', verbose_name="Servicio Asociado"
    )
    numero_ticket = models.CharField(max_length=100, db_index=True, verbose_name="N° de Ticket / Folio")
    fecha = models.DateField(verbose_name="Fecha de Retiro")
    faena_area = models.CharField(max_length=200, blank=True, verbose_name="Instalación / Faena / Área")
    tipo_servicio = models.CharField(
        max_length=200, blank=True, verbose_name="Tipo de Servicio / Área",
        help_text="Ej: Áreas Productivas, Bodega APD, Puntos Verdes, Retiro Doméstico, Recepción de Ramplas"
    )
    tipo_residuo = models.CharField(
        max_length=200, default='Reciclaje', verbose_name="Tipo de Residuo General",
        help_text="Ej: Reciclaje, Residuos Domésticos, Chatarra"
    )
    peso_total_ticket = models.DecimalField(
        max_digits=12, decimal_places=2, verbose_name="Peso Total Báscula (kg)",
        help_text="Peso oficial de pesaje / báscula"
    )
    respaldo_ticket = models.FileField(
        upload_to='tickets_retiro/respaldos/%Y/%m/', blank=True, null=True,
        verbose_name="Comprobante de Pesaje (Foto / PDF)"
    )
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    usuario_registro = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Registrado por"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)

    @property
    def total_kilos_desglosados(self):
        total = self.detalles.aggregate(total=models.Sum('peso_kg'))['total']
        return total if total is not None else 0.0

    @property
    def diferencia_peso(self):
        if self.peso_total_ticket is not None:
            return round(float(self.peso_total_ticket) - float(self.total_kilos_desglosados), 2)
        return 0.0

    @property
    def tiene_desglose(self):
        return self.detalles.exists()

    @property
    def is_cuadrado(self):
        if not self.tiene_desglose:
            return True
        return abs(self.diferencia_peso) < 0.05

    @property
    def es_imagen_respaldo(self):
        if not self.respaldo_ticket:
            return False
        nombre = self.respaldo_ticket.name.lower()
        return any(nombre.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'])

    @property
    def registrado_por(self):
        return self.usuario_registro

    @property
    def detalles_materiales(self):
        return self.detalles

    def __str__(self):
        return f"Ticket N° {self.numero_ticket} — {self.empresa.nombre} ({self.fecha})"

    class Meta:
        db_table = 'tickets_retiro'
        verbose_name = "Ticket de Retiro"
        verbose_name_plural = "Tickets de Retiro"
        ordering = ['-fecha', '-numero_ticket']


class DetalleMaterialTicket(models.Model):
    ticket = models.ForeignKey(
        TicketRetiro, on_delete=models.CASCADE,
        related_name='detalles', verbose_name="Ticket de Retiro"
    )
    material = models.ForeignKey(
        CatalogoMaterialRetiro, on_delete=models.PROTECT,
        related_name='detalles', verbose_name="Material"
    )
    peso_kg = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        verbose_name="Peso (kg)"
    )
    cantidad_unidades = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Cantidad (Unidades)",
        help_text="Opcional: unidades de pallets, tambores, carretes, etc."
    )
    observaciones = models.CharField(max_length=255, blank=True, verbose_name="Observaciones / Detalle")

    def __str__(self):
        return f"{self.material.nombre}: {self.peso_kg} kg — Ticket {self.ticket.numero_ticket}"

    class Meta:
        db_table = 'detalles_material_ticket'
        verbose_name = "Detalle de Material en Ticket"
        verbose_name_plural = "Detalles de Materiales en Tickets"
        ordering = ['material__orden', 'material__nombre']
