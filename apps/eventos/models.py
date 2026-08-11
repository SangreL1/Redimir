from django.db import models

class Evento(models.Model):
    TIPOS_EVENTO = [
        ('recolectado', 'Recolectado en terreno'),
        ('recibido', 'Recibido en bodega'),
        ('procesando', 'Iniciado procesamiento'),
        ('procesado', 'Procesamiento completado'),
        ('vendido', 'Vendido/Entregado'),
        ('cancelado', 'Cancelado'),
    ]
    
    lote = models.ForeignKey('lotes.Lote', on_delete=models.CASCADE, related_name='eventos')
    tipo_evento = models.CharField(max_length=20, choices=TIPOS_EVENTO)
    usuario = models.ForeignKey('usuarios.Usuario', on_delete=models.SET_NULL, null=True)
    
    timestamp = models.DateTimeField(auto_now_add=True)
    descripcion = models.TextField()
    foto = models.ImageField(upload_to='fotos/eventos/%Y/%m/%d/', blank=True)
    ubicacion_gps = models.CharField(max_length=255, blank=True)
    
    class Meta:
        db_table = 'eventos'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.lote.codigo_lote} - {self.tipo_evento}"
