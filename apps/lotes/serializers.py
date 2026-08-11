from rest_framework import serializers
from .models import Lote
from apps.eventos.models import Evento

class EventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evento
        fields = '__all__'

class LoteSerializer(serializers.ModelSerializer):
    eventos = EventoSerializer(many=True, read_only=True)
    
    class Meta:
        model = Lote
        fields = '__all__'
        read_only_fields = ('codigo_lote', 'qr_code', 'estado', 'fecha_recoleccion')
