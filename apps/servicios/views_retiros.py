import os
import re
import datetime
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q, Sum
from django.core.paginator import Paginator
from django.utils import timezone

from .models import TicketRetiro, DetalleMaterialTicket, CatalogoMaterialRetiro
from .forms import TicketRetiroForm, DetalleMaterialTicketForm
from apps.empresas.models import Empresa


def _es_admin(user):
    return getattr(user, 'rol', '') == 'admin' or user.is_staff or user.is_superuser


@login_required
def retiros_lista(request):
    """
    Bandeja de Tickets y Retiros de Residuos.
    Multi-empresa: Los administradores ven todas las empresas; usuarios de empresa ven la suya.
    """
    tickets = TicketRetiro.objects.select_related('empresa').prefetch_related('detalles__material').all().order_by('-fecha', '-id')

    # Restricción multi-empresa
    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        tickets = tickets.filter(empresa=request.user.empresa)

    # Filtros
    q = request.GET.get('q', '').strip()
    empresa_id = request.GET.get('empresa', '').strip()
    faena_f = request.GET.get('faena', '').strip()
    servicio_f = request.GET.get('tipo_servicio', '').strip()
    residuo_f = request.GET.get('tipo_residuo', '').strip()
    desde_f = request.GET.get('desde', '').strip()
    hasta_f = request.GET.get('hasta', '').strip()

    if q:
        tickets = tickets.filter(
            Q(numero_ticket__icontains=q) |
            Q(observaciones__icontains=q) |
            Q(empresa__nombre__icontains=q) |
            Q(faena_area__icontains=q)
        )
    if empresa_id:
        tickets = tickets.filter(empresa_id=empresa_id)
    if faena_f:
        tickets = tickets.filter(faena_area__icontains=faena_f)
    if servicio_f:
        tickets = tickets.filter(tipo_servicio__icontains=servicio_f)
    if residuo_f:
        tickets = tickets.filter(tipo_residuo__icontains=residuo_f)
    if desde_f:
        tickets = tickets.filter(fecha__gte=desde_f)
    if hasta_f:
        tickets = tickets.filter(fecha__lte=hasta_f)

    # Listas para opciones de filtros
    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        empresas_list = [request.user.empresa]
    else:
        empresas_list = Empresa.objects.filter(activa=True).order_by('nombre')

    servicios_list = TicketRetiro.objects.values_list('tipo_servicio', flat=True).exclude(tipo_servicio__isnull=True).exclude(tipo_servicio='').distinct().order_by('tipo_servicio')
    residuos_list = TicketRetiro.objects.values_list('tipo_residuo', flat=True).exclude(tipo_residuo__isnull=True).exclude(tipo_residuo='').distinct().order_by('tipo_residuo')

    total_tickets = tickets.count()
    total_kilos = tickets.aggregate(total=Sum('peso_total_ticket'))['total'] or Decimal('0.00')

    detalles_qs = DetalleMaterialTicket.objects.filter(ticket__in=tickets)
    kilos_reciclaje = detalles_qs.filter(material__categoria='Reciclaje').aggregate(total=Sum('peso_kg'))['total'] or Decimal('0.00')
    kilos_maderas = detalles_qs.filter(material__categoria='Madera').aggregate(total=Sum('peso_kg'))['total'] or Decimal('0.00')
    kilos_domesticos = detalles_qs.filter(material__categoria='Domestico').aggregate(total=Sum('peso_kg'))['total'] or Decimal('0.00')

    tickets_con_respaldo = tickets.exclude(respaldo_ticket='').exclude(respaldo_ticket__isnull=True).count()
    pct_respaldo = round((tickets_con_respaldo / total_tickets * 100), 1) if total_tickets > 0 else 0

    paginator = Paginator(tickets, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'tickets': page_obj,
        'total_tickets': total_tickets,
        'total_kilos': total_kilos,
        'kilos_reciclaje': kilos_reciclaje,
        'kilos_maderas': kilos_maderas,
        'kilos_domesticos': kilos_domesticos,
        'pct_respaldo': pct_respaldo,
        'empresas_list': empresas_list,
        'servicios_list': servicios_list,
        'residuos_list': residuos_list,
        'filtros': {
            'q': q,
            'empresa': empresa_id,
            'faena': faena_f,
            'tipo_servicio': servicio_f,
            'tipo_residuo': residuo_f,
            'desde': desde_f,
            'hasta': hasta_f,
        }
    }
    return render(request, 'servicios/retiros_lista.html', context)


@login_required
def retiro_crear(request):
    """
    Ingreso de nuevo retiro con desglose dinámico de materiales.
    """
    materiales_catalogo = CatalogoMaterialRetiro.objects.filter(activo=True).order_by('orden', 'nombre')

    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        empresas_disponibles = [request.user.empresa]
        empresa_default = request.user.empresa
    else:
        empresas_disponibles = Empresa.objects.filter(activa=True).order_by('nombre')
        empresa_default = empresas_disponibles.first()

    if request.method == 'POST':
        form = TicketRetiroForm(request.POST, request.FILES)
        if form.is_valid():
            ticket = form.save(commit=False)
            if getattr(request.user, 'rol', '') == 'empresa':
                ticket.empresa = request.user.empresa
            ticket.usuario_registro = request.user
            ticket.save()

            # Guardar líneas dinámicas de materiales
            mat_ids = request.POST.getlist('material_id[]')
            pesos = request.POST.getlist('peso_kg[]')
            cantidades = request.POST.getlist('cantidad_unidades[]')
            observaciones_items = request.POST.getlist('obs_detalle[]')

            for i in range(len(mat_ids)):
                mat_id = mat_ids[i]
                if not mat_id:
                    continue
                try:
                    mat_obj = CatalogoMaterialRetiro.objects.get(pk=mat_id)
                except CatalogoMaterialRetiro.DoesNotExist:
                    continue

                peso_val = Decimal('0.00')
                if i < len(pesos) and pesos[i].strip():
                    try:
                        peso_val = Decimal(pesos[i].strip())
                    except Exception:
                        peso_val = Decimal('0.00')

                cant_val = None
                if i < len(cantidades) and cantidades[i].strip():
                    try:
                        cant_val = Decimal(cantidades[i].strip())
                    except Exception:
                        cant_val = None

                obs_val = observaciones_items[i].strip() if i < len(observaciones_items) else ''

                if (peso_val and peso_val > 0) or (cant_val and cant_val > 0):
                    DetalleMaterialTicket.objects.create(
                        ticket=ticket,
                        material=mat_obj,
                        peso_kg=peso_val,
                        cantidad_unidades=cant_val,
                        observaciones=obs_val
                    )

            messages.success(request, f"✅ Ticket N° {ticket.numero_ticket} registrado exitosamente.")
            return redirect('retiro-detalle', pk=ticket.pk)
        else:
            messages.error(request, "⚠️ Por favor corrige los errores en el formulario.")
    else:
        form = TicketRetiroForm(initial={
            'fecha': timezone.now().date(),
            'empresa': empresa_default,
            'tipo_residuo': 'Reciclaje',
            'tipo_servicio': 'Áreas Productivas'
        })

    return render(request, 'servicios/retiro_form.html', {
        'form': form,
        'materiales_catalogo': materiales_catalogo,
        'empresas_disponibles': empresas_disponibles,
        'modo_edicion': False,
    })


@login_required
def retiro_editar(request, pk):
    """
    Edición de un ticket existente y actualización de sus materiales.
    """
    ticket = get_object_or_404(TicketRetiro, pk=pk)
    materiales_catalogo = CatalogoMaterialRetiro.objects.filter(activo=True).order_by('orden', 'nombre')

    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        if ticket.empresa != request.user.empresa:
            messages.error(request, "Sin permisos para editar retiros de otra empresa.")
            return redirect('retiros-lista')
        empresas_disponibles = [request.user.empresa]
    else:
        empresas_disponibles = Empresa.objects.filter(activa=True).order_by('nombre')

    if request.method == 'POST':
        form = TicketRetiroForm(request.POST, request.FILES, instance=ticket)
        if form.is_valid():
            ticket = form.save()

            # Reemplazar líneas de desglose
            ticket.detalles.all().delete()

            mat_ids = request.POST.getlist('material_id[]')
            pesos = request.POST.getlist('peso_kg[]')
            cantidades = request.POST.getlist('cantidad_unidades[]')
            observaciones_items = request.POST.getlist('obs_detalle[]')

            for i in range(len(mat_ids)):
                mat_id = mat_ids[i]
                if not mat_id:
                    continue
                try:
                    mat_obj = CatalogoMaterialRetiro.objects.get(pk=mat_id)
                except CatalogoMaterialRetiro.DoesNotExist:
                    continue

                peso_val = Decimal('0.00')
                if i < len(pesos) and pesos[i].strip():
                    try:
                        peso_val = Decimal(pesos[i].strip())
                    except Exception:
                        peso_val = Decimal('0.00')

                cant_val = None
                if i < len(cantidades) and cantidades[i].strip():
                    try:
                        cant_val = Decimal(cantidades[i].strip())
                    except Exception:
                        cant_val = None

                obs_val = observaciones_items[i].strip() if i < len(observaciones_items) else ''

                if (peso_val and peso_val > 0) or (cant_val and cant_val > 0):
                    DetalleMaterialTicket.objects.create(
                        ticket=ticket,
                        material=mat_obj,
                        peso_kg=peso_val,
                        cantidad_unidades=cant_val,
                        observaciones=obs_val
                    )

            messages.success(request, f"✅ Ticket N° {ticket.numero_ticket} actualizado correctamente.")
            return redirect('retiro-detalle', pk=ticket.pk)
        else:
            messages.error(request, "⚠️ Error al guardar las modificaciones.")
    else:
        form = TicketRetiroForm(instance=ticket)

    detalles_existentes = ticket.detalles.select_related('material').all()

    return render(request, 'servicios/retiro_form.html', {
        'form': form,
        'ticket': ticket,
        'detalles_existentes': detalles_existentes,
        'materiales_catalogo': materiales_catalogo,
        'empresas_disponibles': empresas_disponibles,
        'modo_edicion': True,
    })


@login_required
def retiro_detalle(request, pk):
    """
    Ficha de detalle técnico del ticket con visor de comprobante y desglose.
    """
    ticket = get_object_or_404(TicketRetiro.objects.select_related('empresa').prefetch_related('detalles__material'), pk=pk)

    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        if ticket.empresa != request.user.empresa:
            messages.error(request, "Acceso no permitido.")
            return redirect('retiros-lista')

    detalles = list(ticket.detalles.all())
    peso_total = float(ticket.peso_total_ticket or 1.0)
    for d in detalles:
        d.porcentaje = round((float(d.peso_kg) / peso_total * 100), 1) if peso_total > 0 else 0

    return render(request, 'servicios/retiro_detalle.html', {
        'ticket': ticket,
        'detalles': detalles,
    })


@login_required
def retiro_eliminar(request, pk):
    """
    Eliminación de ticket.
    """
    ticket = get_object_or_404(TicketRetiro, pk=pk)

    if not _es_admin(request.user):
        messages.error(request, "Solo administradores pueden eliminar tickets.")
        return redirect('retiros-lista')

    numero = ticket.numero_ticket
    if request.method == 'POST':
        ticket.delete()
        messages.success(request, f"🗑️ Ticket N° {numero} eliminado exitosamente.")
        return redirect('retiros-lista')

    return render(request, 'servicios/retiro_confirmar_eliminar.html', {'ticket': ticket})


@login_required
def retiros_informe(request):
    """
    Generador de Informes Matriz de Residuos por Empresa y Fecha.
    """
    empresa_id = request.GET.get('empresa', '').strip()
    faena = request.GET.get('faena', '').strip()
    tipo_servicio = request.GET.get('tipo_servicio', '').strip()
    tipo_residuo = request.GET.get('tipo_residuo', '').strip()
    desde = request.GET.get('desde', '').strip()
    hasta = request.GET.get('hasta', '').strip()

    qs = TicketRetiro.objects.select_related('empresa').prefetch_related('detalles__material').all().order_by('fecha', 'id')

    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        qs = qs.filter(empresa=request.user.empresa)
        empresas_list = [request.user.empresa]
        empresa_actual = request.user.empresa
    else:
        empresas_list = Empresa.objects.filter(activa=True).order_by('nombre')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
            empresa_actual = Empresa.objects.filter(id=empresa_id).first()
        else:
            empresa_actual = None

    if faena:
        qs = qs.filter(faena_area__icontains=faena)
    if tipo_servicio:
        qs = qs.filter(tipo_servicio__icontains=tipo_servicio)
    if tipo_residuo:
        qs = qs.filter(tipo_residuo__icontains=tipo_residuo)
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

    tickets = list(qs)

    materiales_presentes_ids = DetalleMaterialTicket.objects.filter(ticket__in=qs).values_list('material_id', flat=True).distinct()
    columnas_materiales = list(CatalogoMaterialRetiro.objects.filter(id__in=materiales_presentes_ids).order_by('orden', 'nombre'))

    matriz_filas = []
    totales_materiales = {mat.id: {'peso': Decimal('0.00'), 'cantidad': Decimal('0.00')} for mat in columnas_materiales}
    total_peso_bascula = Decimal('0.00')

    for t in tickets:
        total_peso_bascula += (t.peso_total_ticket or Decimal('0.00'))
        det_map = {d.material_id: d for d in t.detalles.all()}
        
        celdas = []
        for mat in columnas_materiales:
            det = det_map.get(mat.id)
            if det:
                peso = det.peso_kg or Decimal('0.00')
                cant = det.cantidad_unidades
                totales_materiales[mat.id]['peso'] += peso
                if cant:
                    totales_materiales[mat.id]['cantidad'] += cant
                celdas.append({
                    'material_id': mat.id,
                    'peso': peso if peso > 0 else None,
                    'cantidad': cant if cant and cant > 0 else None,
                })
            else:
                celdas.append({
                    'material_id': mat.id,
                    'peso': None,
                    'cantidad': None,
                })

        matriz_filas.append({
            'ticket': t,
            'celdas': celdas,
        })

    servicios_list = TicketRetiro.objects.values_list('tipo_servicio', flat=True).exclude(tipo_servicio__isnull=True).exclude(tipo_servicio='').distinct().order_by('tipo_servicio')

    context = {
        'tickets_count': len(tickets),
        'columnas_materiales': columnas_materiales,
        'matriz_filas': matriz_filas,
        'totales_materiales': totales_materiales,
        'total_peso_bascula': total_peso_bascula,
        'empresas_list': empresas_list,
        'empresa_actual': empresa_actual,
        'servicios_list': servicios_list,
        'filtros': {
            'empresa': empresa_id,
            'faena': faena,
            'tipo_servicio': tipo_servicio,
            'tipo_residuo': tipo_residuo,
            'desde': desde,
            'hasta': hasta,
        }
    }
    return render(request, 'servicios/retiros_informe.html', context)


@login_required
def exportar_retiros_excel(request):
    """
    Descarga del Informe Consolidado en Excel (.xlsx) con openpyxl.
    """
    empresa_id = request.GET.get('empresa', '').strip()
    faena = request.GET.get('faena', '').strip()
    tipo_servicio = request.GET.get('tipo_servicio', '').strip()
    tipo_residuo = request.GET.get('tipo_residuo', '').strip()
    desde = request.GET.get('desde', '').strip()
    hasta = request.GET.get('hasta', '').strip()

    qs = TicketRetiro.objects.select_related('empresa').prefetch_related('detalles__material').all().order_by('fecha', 'id')

    empresa_nombre = "TODOS"
    if getattr(request.user, 'rol', '') == 'empresa' and getattr(request.user, 'empresa', None):
        qs = qs.filter(empresa=request.user.empresa)
        empresa_nombre = request.user.empresa.nombre
    elif empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
        emp = Empresa.objects.filter(id=empresa_id).first()
        if emp:
            empresa_nombre = emp.nombre

    if faena:
        qs = qs.filter(faena_area__icontains=faena)
    if tipo_servicio:
        qs = qs.filter(tipo_servicio__icontains=tipo_servicio)
    if tipo_residuo:
        qs = qs.filter(tipo_residuo__icontains=tipo_residuo)
    if desde:
        qs = qs.filter(fecha__gte=desde)
    if hasta:
        qs = qs.filter(fecha__lte=hasta)

    tickets = list(qs)

    materiales_presentes_ids = DetalleMaterialTicket.objects.filter(ticket__in=qs).values_list('material_id', flat=True).distinct()
    columnas_materiales = list(CatalogoMaterialRetiro.objects.filter(id__in=materiales_presentes_ids).order_by('orden', 'nombre'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Consolidado Retiros"

    # Estilos Corporativos Redimir (#006BB8 y #95BF3C)
    font_title = Font(name="Calibri", size=14, bold=True, color="006BB8")
    font_sub = Font(name="Calibri", size=10, italic=True, color="475569")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_total = Font(name="Calibri", size=11, bold=True, color="000000")
    font_data = Font(name="Calibri", size=10)

    fill_header_main = PatternFill(start_color="006BB8", end_color="006BB8", fill_type="solid")
    fill_header_mat = PatternFill(start_color="95BF3C", end_color="95BF3C", fill_type="solid")
    fill_total = PatternFill(start_color="FEF08A", end_color="FEF08A", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )
    total_border = Border(
        top=Side(style='thin', color='000000'),
        bottom=Side(style='double', color='000000')
    )

    ws.merge_cells('A1:G1')
    ws['A1'] = "REDIMIR SPA — INFORME CONSOLIDADO DE RETIRO DE RESIDUOS"
    ws['A1'].font = font_title

    subtitulo_info = f"Empresa / Cliente: {empresa_nombre} | Faena: {faena or 'TODAS'} | Período: {desde or 'Inicio'} al {hasta or 'Cierre'}"
    ws.merge_cells('A2:G2')
    ws['A2'] = subtitulo_info
    ws['A2'].font = font_sub

    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[4].height = 26

    headers = ['N° FOLIO / TICKET', 'FECHA', 'EMPRESA / CLIENTE', 'TIPO SERVICIO', 'TIPO RESIDUO', 'PESO TOTAL BÁSCULA (kg)']
    
    col_mapping = []
    for mat in columnas_materiales:
        if mat.unidad_medida == 'kg_un':
            headers.append(f"{mat.nombre} (kg)")
            col_mapping.append((mat, 'peso'))
            headers.append(f"Cant. {mat.nombre} (un)")
            col_mapping.append((mat, 'cantidad'))
        elif mat.unidad_medida == 'un':
            headers.append(f"{mat.nombre} (un)")
            col_mapping.append((mat, 'cantidad'))
        else:
            headers.append(f"{mat.nombre} (kg)")
            col_mapping.append((mat, 'peso'))

    headers.append('OBSERVACIONES')

    start_row = 4
    for c_idx, h_text in enumerate(headers, 1):
        cell = ws.cell(start_row, c_idx, h_text)
        cell.font = font_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if c_idx <= 6:
            cell.fill = fill_header_main
        else:
            cell.fill = fill_header_mat
        cell.border = thin_border

    curr_row = start_row + 1
    for t in tickets:
        det_map = {d.material_id: d for d in t.detalles.all()}
        
        ws.cell(curr_row, 1, t.numero_ticket).alignment = Alignment(horizontal="center")
        ws.cell(curr_row, 2, t.fecha.strftime('%d/%m/%Y')).alignment = Alignment(horizontal="center")
        ws.cell(curr_row, 3, t.empresa.nombre)
        ws.cell(curr_row, 4, t.tipo_servicio or '')
        ws.cell(curr_row, 5, t.tipo_residuo or '')
        
        c_peso = ws.cell(curr_row, 6, float(t.peso_total_ticket or 0))
        c_peso.number_format = '#,##0.0'
        c_peso.alignment = Alignment(horizontal="right")

        c_idx = 7
        for mat, metric in col_mapping:
            det = det_map.get(mat.id)
            val = None
            if det:
                if metric == 'peso' and det.peso_kg and det.peso_kg > 0:
                    val = float(det.peso_kg)
                elif metric == 'cantidad' and det.cantidad_unidades and det.cantidad_unidades > 0:
                    val = float(det.cantidad_unidades)
            
            cell_m = ws.cell(curr_row, c_idx, val if val is not None else "")
            if val is not None:
                cell_m.number_format = '#,##0.0' if metric == 'peso' else '#,##0'
                cell_m.alignment = Alignment(horizontal="right")
            c_idx += 1

        ws.cell(curr_row, c_idx, t.observaciones or "")

        for c in range(1, len(headers) + 1):
            cell = ws.cell(curr_row, c)
            cell.font = font_data
            cell.border = thin_border

        curr_row += 1

    total_row = curr_row
    ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=5)
    cell_tot_lbl = ws.cell(total_row, 1, "TOTALES ACUMULADOS")
    cell_tot_lbl.font = font_total
    cell_tot_lbl.alignment = Alignment(horizontal="center", vertical="center")
    cell_tot_lbl.fill = fill_total

    col_letter_bascula = get_column_letter(6)
    cell_tot_bascula = ws.cell(total_row, 6, f"=SUM({col_letter_bascula}{start_row + 1}:{col_letter_bascula}{total_row - 1})")
    cell_tot_bascula.font = font_total
    cell_tot_bascula.fill = fill_total
    cell_tot_bascula.number_format = '#,##0.0'
    cell_tot_bascula.border = total_border

    for c_idx in range(7, len(headers)):
        c_letter = get_column_letter(c_idx)
        cell_tot = ws.cell(total_row, c_idx, f"=SUM({c_letter}{start_row + 1}:{c_letter}{total_row - 1})")
        cell_tot.font = font_total
        cell_tot.fill = fill_total
        cell_tot.number_format = '#,##0.0'
        cell_tot.border = total_border

    cell_empty = ws.cell(total_row, len(headers), "")
    cell_empty.fill = fill_total
    cell_empty.border = total_border

    for c in range(1, 6):
        ws.cell(total_row, c).border = total_border

    ws.row_dimensions[total_row].height = 24

    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or '')
            if cell.row in [1, 2]:
                continue
            max_len = max(max_len, len(val_str))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    filename_empresa = re.sub(r'[^a-zA-Z0-9_-]', '_', empresa_nombre)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    filename = f"REDIMIR_Informe_Retiros_{filename_empresa}_{timestamp}.xlsx"

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


@login_required
def api_materiales_retiro(request):
    materiales = CatalogoMaterialRetiro.objects.filter(activo=True).order_by('orden', 'nombre').values(
        'id', 'nombre', 'codigo', 'categoria', 'unidad_medida'
    )
    return JsonResponse({'materiales': list(materiales)})
