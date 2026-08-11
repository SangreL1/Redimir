from django.db import models
from django.utils import timezone


class Notificacion(models.Model):
    TIPOS = [
        ('nueva_solicitud', 'Nueva Solicitud de Recolección'),
        ('solicitud_asignada', 'Te Asignaron una Solicitud'),
        ('recoleccion_confirmada', 'Recolección Confirmada'),
        ('sistema', 'Mensaje del Sistema'),
    ]

    usuario = models.ForeignKey(
        'usuarios.Usuario', on_delete=models.CASCADE,
        related_name='notificaciones'
    )
    tipo = models.CharField(max_length=30, choices=TIPOS)
    titulo = models.CharField(max_length=200)
    mensaje = models.TextField()
    url_destino = models.CharField(max_length=255, blank=True)

    leida = models.BooleanField(default=False)
    fecha_lectura = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notificaciones'
        ordering = ['-fecha_creacion']
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return f"Para {self.usuario.nombre}: {self.titulo}"

    def marcar_leida(self):
        if not self.leida:
            self.leida = True
            self.fecha_lectura = timezone.now()
            self.save(update_fields=['leida', 'fecha_lectura'])
