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
