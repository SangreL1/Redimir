from django import forms
from .models import TicketRetiro, DetalleMaterialTicket, CatalogoMaterialRetiro
from apps.empresas.models import Empresa


class TicketRetiroForm(forms.ModelForm):
    class Meta:
        model = TicketRetiro
        fields = [
            'empresa', 'numero_ticket', 'fecha', 'faena_area',
            'operador_responsable',
            'tipo_servicio', 'tipo_residuo', 'peso_total_ticket',
            'respaldo_ticket', 'observaciones',
        ]
        widgets = {
            'empresa': forms.Select(attrs={'class': 'form-select'}),
            'numero_ticket': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. 148786', 'autocomplete': 'off'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'faena_area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Planta Prillex, Open Calama'}),
            'operador_responsable': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej. Juan Pérez / Operador en turno',
                'list': 'operadoresList'
            }),
            'tipo_servicio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Áreas Productivas, Bodega APD, Puntos Verdes'}),
            'tipo_residuo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej. Reciclaje, Residuos Domésticos'}),
            'peso_total_ticket': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': '0.00', 'step': 'any'}),
            'respaldo_ticket': forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*,.pdf'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Observaciones adicionales...'}),
        }
        labels = {
            'empresa': 'Empresa / Cliente *',
            'numero_ticket': 'N° de Ticket / Folio *',
            'fecha': 'Fecha del Retiro *',
            'faena_area': 'Instalación / Faena / Área',
            'operador_responsable': 'Operador / Persona Responsable',
            'tipo_servicio': 'Tipo de Servicio',
            'tipo_residuo': 'Clasificación General del Residuo',
            'peso_total_ticket': 'Peso Total Báscula (kg) *',
            'respaldo_ticket': 'Comprobante de Pesaje (Foto / PDF) *',
            'observaciones': 'Observaciones',
        }

    def clean_numero_ticket(self):
        numero = self.cleaned_data.get('numero_ticket')
        if numero:
            numero = str(numero).strip()
            qs = TicketRetiro.objects.filter(numero_ticket__iexact=numero)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            existente = qs.select_related('empresa').first()
            if existente:
                fecha_str = existente.fecha.strftime('%d/%m/%Y') if existente.fecha else 'fecha registrada'
                raise forms.ValidationError(
                    f"⚠️ El N° de Ticket Báscula '{numero}' ya existe en el sistema. "
                    f"Fue registrado el {fecha_str} para la empresa '{existente.empresa.nombre}'. "
                    f"Verifica el número de folio para evitar duplicados."
                )
        return numero

    def clean_peso_total_ticket(self):
        val = self.cleaned_data.get('peso_total_ticket')
        if val is None:
            raw = self.data.get('peso_total_ticket', '')
            if raw:
                raw = str(raw).replace(',', '.').strip()
                try:
                    from decimal import Decimal
                    return Decimal(raw)
                except Exception:
                    raise forms.ValidationError('Ingresa un peso válido.')
        return val

    def clean_respaldo_ticket(self):
        respaldo = self.cleaned_data.get('respaldo_ticket')
        if not respaldo and not (self.instance and self.instance.pk and self.instance.respaldo_ticket):
            raise forms.ValidationError('El comprobante o fotografía del Ticket de Pesaje es obligatorio.')
        return respaldo


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
