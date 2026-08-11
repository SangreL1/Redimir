"""
CALCULADORA DE ECO-EQUIVALENCIA - REDIMIR
Factores configurables por material para calcular ahorro ambiental.
"""
from django.db import models
from django.utils import timezone


class FactorEcoEquivalencia(models.Model):
    """
    Factores de eco-equivalencia configurables por material.
    Permite al administrador ajustar los factores sin tocar código.

    Fórmulas aplicadas en RegistroReciclables.calcular_eco_equivalencia():
    - Agua (L)      = kg × factor_agua_lxkg
    - CO2 (kg)      = kg × factor_co2_kgxkg
    - Energía (kWh) = kg × factor_energia_kwhxkg
    - Petróleo (L)  = kg × factor_petroleo_lxkg
    - Árboles       = kg × factor_arboles_kgxkg
    """
    MATERIALES = [
        ('carton',   'Cartón'),
        ('papel',    'Papel'),
        ('pet',      'Plástico PET'),
        ('latas',    'Latas de Aluminio'),
        ('film',     'Film LDPE'),
        ('carretes', 'Carretes'),
        ('sunchos',  'Sunchos'),
        ('vidrio',   'Vidrio'),
        ('tetrapak', 'Tetrapak'),
        ('plastico', 'Plástico general'),
        ('pallets',  'Pallets'),
        ('otro',     'Otro'),
    ]

    material         = models.CharField(max_length=30, choices=MATERIALES, verbose_name='Material')

    # Factores por kg de material
    factor_agua_lxkg      = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                 verbose_name='Ahorro de Agua (L/kg)')
    factor_co2_kgxkg      = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                 verbose_name='Ahorro CO₂ (kg/kg)')
    factor_energia_kwhxkg = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                 verbose_name='Ahorro de Energía (kWh/kg)')
    factor_petroleo_lxkg  = models.DecimalField(max_digits=12, decimal_places=4, default=0,
                                                 verbose_name='Ahorro de Petróleo (L/kg)')
    factor_arboles_kgxkg  = models.DecimalField(max_digits=12, decimal_places=6, default=0,
                                                 verbose_name='Árboles no talados (árbol/kg)')

    # Versionado e historial
    version             = models.IntegerField(default=1, verbose_name='Versión del Factor')
    usuario_modificador = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True,
                                             verbose_name='Usuario Modificador')
    fecha_modificacion  = models.DateTimeField(auto_now=True)

    # Vigencia
    fecha_inicio  = models.DateField(default=timezone.now, verbose_name='Vigente desde')
    fecha_fin     = models.DateField(null=True, blank=True, verbose_name='Vigente hasta')
    activo        = models.BooleanField(default=True)

    notas = models.TextField(blank=True, verbose_name='Notas / fuente del factor')

    class Meta:
        db_table = 'factores_eco_equivalencia'
        ordering = ['material', '-fecha_inicio']
        verbose_name = 'Factor Eco-Equivalencia'
        verbose_name_plural = 'Factores Eco-Equivalencia'

    def __str__(self):
        return f"{self.get_material_display()} — Agua:{self.factor_agua_lxkg} L/kg | CO2:{self.factor_co2_kgxkg} kg/kg"

    @classmethod
    def get_factor_activo(cls, material):
        """Obtiene el factor vigente más reciente para un material dado."""
        hoy = timezone.now().date()
        return cls.objects.filter(
            material=material,
            activo=True,
            fecha_inicio__lte=hoy,
        ).filter(
            models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=hoy)
        ).order_by('-fecha_inicio').first()

    @classmethod
    def calcular_consolidado(cls, registros_qs):
        """
        Calcula eco-equivalencia total para un queryset de RegistroReciclables.
        Retorna dict con totales.
        """
        from decimal import Decimal
        totales = {
            'kg_total':        Decimal('0'),
            'agua_L':          Decimal('0'),
            'co2_kg':          Decimal('0'),
            'energia_kwh':     Decimal('0'),
            'petroleo_L':      Decimal('0'),
            'arboles':         Decimal('0'),
            'desglose':        {},
        }
        for reg in registros_qs:
            kg = reg.cantidad_kg or Decimal('0')
            totales['kg_total'] += kg
            totales['agua_L']     += reg.eco_agua_L      or Decimal('0')
            totales['co2_kg']     += reg.eco_co2_kg      or Decimal('0')
            totales['energia_kwh'] += reg.eco_energia_kwh or Decimal('0')
            totales['petroleo_L'] += reg.eco_petroleo_L  or Decimal('0')
            totales['arboles']    += reg.eco_arboles      or Decimal('0')

            mat = reg.get_material_display()
            totales['desglose'][mat] = float(totales['desglose'].get(mat, 0)) + float(kg)

        return totales


def poblar_factores_defecto():
    """
    Datos iniciales de factores basados en el prompt y documentos Redimir.
    Ejecutar: from apps.calculadora.models import poblar_factores_defecto; poblar_factores_defecto()
    """
    from decimal import Decimal
    factores_defecto = [
        # Plástico / PET
        {'material': 'pet',      'agua': 36.26, 'co2': 2.5, 'energia': 5.0, 'petroleo': 2.0, 'arboles': 0.0},
        {'material': 'plastico', 'agua': 36.26, 'co2': 2.5, 'energia': 5.0, 'petroleo': 2.0, 'arboles': 0.0},
        {'material': 'film',     'agua': 36.26, 'co2': 2.5, 'energia': 5.0, 'petroleo': 2.0, 'arboles': 0.0},
        {'material': 'sunchos',  'agua': 36.26, 'co2': 2.5, 'energia': 5.0, 'petroleo': 2.0, 'arboles': 0.0},
        # Cartón / Papel (1 ton = 270,000L agua, 7000kWh, 17 árboles)
        {'material': 'carton',   'agua': 270.0, 'co2': 0.0, 'energia': 7.0,  'petroleo': 0.0, 'arboles': 0.017},
        {'material': 'papel',    'agua': 270.0, 'co2': 0.0, 'energia': 7.0,  'petroleo': 0.0, 'arboles': 0.017},
        {'material': 'tetrapak', 'agua': 270.0, 'co2': 0.0, 'energia': 7.0,  'petroleo': 0.0, 'arboles': 0.017},
        # Vidrio (1 ton = 670 kg CO2, 1300 kWh)
        {'material': 'vidrio',   'agua': 0.0,   'co2': 0.67,'energia': 1.3,  'petroleo': 0.0, 'arboles': 0.0},
        # Latas aluminio
        {'material': 'latas',    'agua': 0.0,   'co2': 9.0, 'energia': 14.0, 'petroleo': 0.0, 'arboles': 0.0},
        # Pallets (10 pallets = 1 árbol → 1 pallet = 0.1 árbol; estimamos 25 kg/pallet)
        {'material': 'pallets',  'agua': 50.0,  'co2': 0.0, 'energia': 1.0,  'petroleo': 0.0, 'arboles': 0.004},
        # Carretes
        {'material': 'carretes', 'agua': 36.26, 'co2': 2.5, 'energia': 5.0,  'petroleo': 2.0, 'arboles': 0.0},
    ]
    from django.utils import timezone
    for f in factores_defecto:
        FactorEcoEquivalencia.objects.get_or_create(
            material=f['material'],
            fecha_inicio=timezone.now().date(),
            defaults={
                'factor_agua_lxkg':      f['agua'],
                'factor_co2_kgxkg':      f['co2'],
                'factor_energia_kwhxkg': f['energia'],
                'factor_petroleo_lxkg':  f['petroleo'],
                'factor_arboles_kgxkg':  f['arboles'],
                'activo': True,
                'notas': 'Factor inicial según documento Redimir / prompt',
            }
        )
    print("[OK] Factores eco-equivalencia creados correctamente.")
