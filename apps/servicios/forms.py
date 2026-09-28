from django import forms
from .models import TicketRetiro, DetalleMaterialTicket, CatalogoMaterialRetiro
from apps.empresas.models import Empresa


class TicketRetiroForm(forms.ModelForm):
    class Meta:
        model = TicketRetiro
        fields = [
            'empresa', 'numero_ticket', 'fecha', 'faena_area',
            'tipo_servicio', 'tipo_residuo', 'peso_total_ticket',
            'respaldo_ticket', 'observaciones',
        ]
        widgets = {
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'numero_ticket': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 148786'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'faena_area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Planta Prillex, Open Calama'}),
            'tipo_servicio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Áreas Productivas, Bodega APD, Puntos Verdes'}),
            'tipo_residuo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Reciclaje, Residuos Domésticos'}),
            'peso_total_ticket': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.1'}),
            'respaldo_ticket': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones adicionales...'}),
        }
        labels = {
            'empresa': 'Empresa / Cliente *',
            'numero_ticket': 'N° de Ticket / Folio *',
            'fecha': 'Fecha del Retiro *',
            'faena_area': 'Instalación / Faena / Área',
            'tipo_servicio': 'Tipo de Servicio',
            'tipo_residuo': 'Clasificación General del Residuo',
            'peso_total_ticket': 'Peso Total Báscula (kg) *',
            'respaldo_ticket': 'Comprobante de Pesaje (Foto / PDF)',
            'observaciones': 'Observaciones',
        }


class DetalleMaterialTicketForm(forms.ModelForm):
    class Meta:
        model = DetalleMaterialTicket
        fields = ['material', 'peso_kg', 'cantidad_unidades', 'observaciones']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select'}),
            'peso_kg': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': '0.1'}),
            'cantidad_unidades': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Unidades', 'step': '1'}),
            'observaciones': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nota/obs'}),
        }
