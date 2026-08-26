from django.db import models
import qrcode
from io import BytesIO
from django.core.files import File

class Lote(models.Model):
    TIPOS_RESIDUO = [
        ('plastico', 'Plástico'),
        ('metal', 'Metal'),
        ('papel', 'Papel/Cartón'),
        ('vidrio', 'Vidrio'),
        ('organico', 'Orgánico'),
        ('basura', 'RSD / Basura General'),
        ('escombros', 'Escombros / RESCON'),
        ('mixto', 'Mixto / Varios'),
    ]
    
    ESTADOS = [
        ('recolectado', 'Recolectado'),
        ('recibido', 'Recibido en Bodega'),
        ('procesando', 'En Procesamiento'),
        ('procesado', 'Procesado'),
        ('vendido', 'Vendido'),
    ]
    
    codigo_lote = models.CharField(max_length=50, unique=True, blank=True)
    qr_code = models.CharField(max_length=255, blank=True)
    
    empresa_origen = models.ForeignKey('empresas.Empresa', on_delete=models.CASCADE, related_name='lotes')
    operador = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, related_name='lotes_recolectados')
    tipo_residuo = models.CharField(max_length=50, choices=TIPOS_RESIDUO, default='mixto')
    cantidad_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    fecha_recoleccion = models.DateTimeField(auto_now_add=True)
    foto_recoleccion = models.ImageField(upload_to='fotos/recolecciones/%Y/%m/%d/', null=True, blank=True)
    foto_ticket = models.ImageField(upload_to='fotos/tickets/%Y/%m/%d/', null=True, blank=True)
    foto_camion = models.ImageField(upload_to='fotos/camion/%Y/%m/%d/', null=True, blank=True)
    observaciones_recoleccion = models.TextField(blank=True)
    
    ubicacion_gps = models.CharField(max_length=255, blank=True)
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='recolectado')
    
    fecha_recepcion_bodega = models.DateTimeField(null=True, blank=True)
    usuario_recepcion = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='lotes_recibidos')
    
    fecha_procesamiento = models.DateTimeField(null=True, blank=True)
    usuario_procesamiento = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='lotes_procesados')
    peso_final_procesado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    foto_procesamiento = models.ImageField(upload_to='fotos/procesamiento/%Y/%m/%d/', null=True, blank=True)
    
    fecha_venta = models.DateTimeField(null=True, blank=True)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cliente_venta = models.CharField(max_length=150, blank=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'lotes'
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        return f"{self.codigo_lote} - {self.empresa_origen.nombre} ({self.tipo_residuo})"
    
    def save(self, *args, **kwargs):
        is_new = not self.pk
        if not self.codigo_lote:
            from datetime import datetime
            fecha = datetime.now().strftime("%Y%m%d")
            contador = Lote.objects.filter(fecha_creacion__date=datetime.now().date()).count() + 1
            self.codigo_lote = f"P-{fecha}-{contador:04d}"
        
        if not self.qr_code:
            self.qr_code = self.codigo_lote
            
        super().save(*args, **kwargs)
        
        from apps.eventos.models import Evento
        if is_new:
            Evento.objects.create(
                lote=self,
                tipo_evento='recolectado',
                usuario=self.operador,
                descripcion=self.observaciones_recoleccion,
                foto=self.foto_recoleccion.name if self.foto_recoleccion else ''
            )
        else:
            if not self.eventos.filter(tipo_evento=self.estado).exists():
                u = None
                if self.estado == 'recibido': u = self.usuario_recepcion
                elif self.estado in ['procesando', 'procesado']: u = self.usuario_procesamiento
                Evento.objects.create(lote=self, tipo_evento=self.estado, usuario=u)

class EvidenciaLote(models.Model):
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='fotos_extra')
    foto = models.ImageField(upload_to='fotos/recolecciones/extra/%Y/%m/%d/')
    fecha_subida = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'lotes_evidencias'
        ordering = ['fecha_subida']


class DetalleLoteResiduo(models.Model):
    lote = models.ForeignKey(Lote, on_delete=models.CASCADE, related_name='detalles_residuos')
    tipo_residuo = models.CharField(max_length=100)
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unidad = models.CharField(max_length=20, default='kg')

    class Meta:
        db_table = 'lotes_detalles_residuos'

    def __str__(self):
        return f"{self.tipo_residuo}: {self.cantidad} {self.unidad}"

