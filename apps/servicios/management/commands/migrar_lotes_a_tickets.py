from django.core.management.base import BaseCommand
from django.db import transaction
from apps.lotes.models import Lote
from apps.servicios.models import TicketRetiro, DetalleMaterialTicket, CatalogoMaterialRetiro


class Command(BaseCommand):
    help = 'Migra de forma segura todos los retiros registrados en Lotes hacia el nuevo sistema de Tickets y Retiros.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Iniciando migración de Lotes hacia Tickets de Retiro..."))

        # Asegurar catálogo básico
        material_escombros, _ = CatalogoMaterialRetiro.objects.get_or_create(
            nombre='Escombros / RESCON',
            defaults={'categoria': 'Otro', 'unidad_medida': 'kg', 'orden': 20}
        )
        material_domesticos = CatalogoMaterialRetiro.objects.filter(nombre__icontains='Doméstic').first()
        if not material_domesticos:
            material_domesticos = CatalogoMaterialRetiro.objects.filter(categoria='Domestico').first()

        material_generales = CatalogoMaterialRetiro.objects.filter(nombre__icontains='General').first()
        if not material_generales:
            material_generales, _ = CatalogoMaterialRetiro.objects.get_or_create(
                nombre='Residuos Generales / Mixto',
                defaults={'categoria': 'Otro', 'unidad_medida': 'kg', 'orden': 25}
            )

        material_plastico = CatalogoMaterialRetiro.objects.filter(nombre__icontains='PET').first()
        material_carton = CatalogoMaterialRetiro.objects.filter(nombre__icontains='Cartón').first()
        material_chatarra = CatalogoMaterialRetiro.objects.filter(nombre__icontains='Chatarra').first()

        MAPA_CATALOGO = {
            'basura': material_domesticos or material_generales,
            'escombros': material_escombros,
            'plastico': material_plastico or material_generales,
            'metal': material_chatarra or material_generales,
            'papel': material_carton or material_generales,
            'organico': material_generales,
            'mixto': material_generales,
        }

        lotes = Lote.objects.select_related('empresa_origen', 'operador').all().order_by('fecha_creacion')
        total_lotes = lotes.count()
        creados = 0
        actualizados = 0

        self.stdout.write(f"Total de lotes encontrados: {total_lotes}")

        with transaction.atomic():
            for lote in lotes:
                folio = lote.codigo_lote
                if not folio:
                    continue

                fecha_retiro = lote.fecha_recoleccion.date() if lote.fecha_recoleccion else lote.fecha_creacion.date()
                tipo_res_display = lote.get_tipo_residuo_display()

                # Seleccionar tipo de servicio predeterminado de la empresa si existe
                servicios_emp = lote.empresa_origen.get_servicios_predeterminados_list()
                if 'escombros' in lote.tipo_residuo.lower():
                    tipo_servicio = 'Escombros / RESCON'
                elif 'basura' in lote.tipo_residuo.lower():
                    tipo_servicio = 'Retiro Doméstico'
                else:
                    tipo_servicio = servicios_emp[0] if servicios_emp else 'Áreas Productivas'

                # Foto de respaldo disponible
                respaldo = lote.foto_ticket or lote.foto_recoleccion or lote.foto_camion

                ticket, created = TicketRetiro.objects.get_or_create(
                    numero_ticket=folio,
                    defaults={
                        'empresa': lote.empresa_origen,
                        'fecha': fecha_retiro,
                        'faena_area': lote.empresa_origen.direccion or 'Instalación Principal',
                        'tipo_servicio': tipo_servicio,
                        'tipo_residuo': tipo_res_display,
                        'peso_total_ticket': lote.cantidad_kg,
                        'respaldo_ticket': respaldo,
                        'observaciones': lote.observaciones_recoleccion or f"Migrado automáticamente desde Lote {folio}",
                        'usuario_registro': lote.operador,
                    }
                )

                if created:
                    creados += 1
                else:
                    actualizados += 1
                    ticket.peso_total_ticket = lote.cantidad_kg
                    if respaldo and not ticket.respaldo_ticket:
                        ticket.respaldo_ticket = respaldo
                    ticket.save()

                # Crear o asegurar detalle del material
                mat_obj = MAPA_CATALOGO.get(lote.tipo_residuo, material_generales)
                if not ticket.detalles.exists() and mat_obj:
                    DetalleMaterialTicket.objects.create(
                        ticket=ticket,
                        material=mat_obj,
                        peso_kg=lote.cantidad_kg,
                        observaciones=f"Detalle {tipo_res_display} ({folio})"
                    )

        self.stdout.write(self.style.SUCCESS(
            f"[OK] Migracion finalizada con exito: {creados} nuevo(s) ticket(s) creados, {actualizados} existente(s) verificados."
        ))
