from django.db import models
from django.utils import timezone

class Certificado(models.Model):
    empresa = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='certificados')
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    
    # Nuevo enlace a Servicios validados
    servicios = models.ManyToManyField('servicios.Servicio', related_name='certificados')
    
    # Resumen de módulos en el certificado
    total_rsd_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_escombros = models.IntegerField(default=0, help_text="Cantidad de retiros de escombros")
    total_reciclables_kg = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    numero_servicios = models.IntegerField(default=0)
    
    desglose_por_tipo = models.JSONField(default=dict)
    
    ESTADOS = [
        ('vigente', 'Vigente / Válido'),
        ('anulado', 'Anulado / Revocado'),
    ]

    codigo_certificado = models.CharField(max_length=50, unique=True, blank=True)
    qr_certificado     = models.CharField(max_length=255, blank=True)
    estado             = models.CharField(max_length=20, choices=ESTADOS, default='vigente')
    hash_sha256        = models.CharField(max_length=64, blank=True, verbose_name='Hash SHA-256 PDF')
    motivo_anulacion   = models.TextField(blank=True, verbose_name='Motivo de Anulación')
    
    archivo_pdf      = models.FileField(upload_to='certificados/%Y/%m/', null=True, blank=True)
    
    generado_por     = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'certificados'
        ordering = ['-fecha_generacion']
    
    def __str__(self):
        return f"CERT-{self.codigo_certificado}"
    
    def save(self, *args, **kwargs):
        if not self.codigo_certificado:
            prefix = "RG-"
            existentes = Certificado.objects.filter(codigo_certificado__startswith=prefix).values_list('codigo_certificado', flat=True)
            max_num = 0
            for code in existentes:
                try:
                    num = int(code.replace(prefix, ''))
                    if num > max_num:
                        max_num = num
                except (ValueError, IndexError):
                    pass
            
            nuevo_num = max_num + 1
            nuevo_codigo = f"{prefix}{nuevo_num:03d}"
            
            while Certificado.objects.filter(codigo_certificado=nuevo_codigo).exists():
                nuevo_num += 1
                nuevo_codigo = f"{prefix}{nuevo_num:03d}"
                
            self.codigo_certificado = nuevo_codigo
            
        super().save(*args, **kwargs)

