"""
GENERADOR DE PDF PARA ESTADOS DE PAGO (EDP) — REDIMIR SpA
Genera el documento formal del Estado de Pago en PDF con ReportLab.
"""
import os
import io
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def generar_pdf_edp(edp):
    """
    Genera el PDF del Estado de Pago oficial de Redimir.
    Retorna bytes del archivo PDF.
    """
    # ── Fuentes ──────────────────────────────────────────────
    fonts_dir  = os.path.join(settings.BASE_DIR, 'static', 'fonts')
    reg_path   = os.path.join(fonts_dir, 'Montserrat-Regular.ttf')
    bold_path  = os.path.join(fonts_dir, 'Montserrat-Bold.ttf')
    xbold_path = os.path.join(fonts_dir, 'Montserrat-ExtraBold.ttf')
    semi_path  = os.path.join(fonts_dir, 'Montserrat-SemiBold.ttf')

    FR = 'Montserrat'           if os.path.exists(reg_path)   else 'Helvetica'
    FB = 'Montserrat-Bold'      if os.path.exists(bold_path)  else 'Helvetica-Bold'
    FX = 'Montserrat-ExtraBold' if os.path.exists(xbold_path) else 'Helvetica-Bold'
    FS = 'Montserrat-SemiBold'  if os.path.exists(semi_path)  else 'Helvetica-Bold'

    if FR == 'Montserrat':
        try:
            pdfmetrics.registerFont(TTFont('Montserrat',           reg_path))
            pdfmetrics.registerFont(TTFont('Montserrat-Bold',      bold_path))
            pdfmetrics.registerFont(TTFont('Montserrat-ExtraBold', xbold_path))
            pdfmetrics.registerFont(TTFont('Montserrat-SemiBold',  semi_path))
        except Exception:
            pass

    # ── Colores ───────────────────────────────────────────────
    AZUL       = HexColor('#006BB8')
    VERDE      = HexColor('#95BF3C')
    NEGRO      = HexColor('#000000')
    GRIS_DARK  = HexColor('#1E293B')
    GRIS_MUTED = HexColor('#64748B')
    GRIS_LINEA = HexColor('#E2E8F0')
    GRIS_FONDO = HexColor('#F8FAFC')
    BLANCO     = HexColor('#FFFFFF')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=14*mm,
        rightMargin=14*mm,
        topMargin=12*mm,
        bottomMargin=12*mm
    )
    elements = []

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    # Estilos
    st_emp_sub = ps('EDPEmpSub', fontName=FR, fontSize=8, leading=11, textColor=GRIS_MUTED)
    st_doc_num = ps('EDPDocNum', fontName=FB, fontSize=9, leading=12, textColor=GRIS_DARK)
    st_date    = ps('EDPDate',   fontName=FB, fontSize=9.5, leading=13, textColor=GRIS_DARK, alignment=2)
    st_badge   = ps('EDPBadge',  fontName=FB, fontSize=8.5, leading=11, textColor=AZUL, alignment=2)
    st_sect_t  = ps('EDPSectT',  fontName=FX, fontSize=10, leading=14, textColor=GRIS_DARK, spaceAfter=4)
    st_cli_lbl = ps('EDPCliLbl', fontName=FB, fontSize=8.5, leading=12, textColor=GRIS_DARK)
    st_cli_val = ps('EDPCliVal', fontName=FR, fontSize=8.5, leading=12, textColor=GRIS_DARK)

    st_th      = ps('EDPTh',     fontName=FX, fontSize=8, leading=10, textColor=BLANCO)
    st_th_c    = ps('EDPThC',    fontName=FX, fontSize=8, leading=10, textColor=BLANCO, alignment=1)
    st_th_r    = ps('EDPThR',    fontName=FX, fontSize=8, leading=10, textColor=BLANCO, alignment=2)

    st_td_desc = ps('EDPTdDesc', fontName=FB, fontSize=8.5, leading=11, textColor=GRIS_DARK)
    st_td_sub  = ps('EDPTdSub',  fontName=FR, fontSize=7.5, leading=10, textColor=GRIS_MUTED)
    st_td_c    = ps('EDPTdC',    fontName=FR, fontSize=8.5, leading=11, textColor=GRIS_DARK, alignment=1)
    st_td_r    = ps('EDPTdR',    fontName=FR, fontSize=8.5, leading=11, textColor=GRIS_DARK, alignment=2)
    st_td_tot  = ps('EDPTdTot',  fontName=FB, fontSize=8.5, leading=11, textColor=GRIS_DARK, alignment=2)

    st_tot_lbl = ps('EDPTotLbl', fontName=FR, fontSize=8.5, leading=12, textColor=GRIS_MUTED, alignment=2)
    st_tot_val = ps('EDPTotVal', fontName=FB, fontSize=8.5, leading=12, textColor=GRIS_DARK, alignment=2)
    st_g_tot_l = ps('EDPGTotL',  fontName=FX, fontSize=11, leading=14, textColor=GRIS_DARK)
    st_g_tot_v = ps('EDPGTotV',  fontName=FX, fontSize=12, leading=15, textColor=GRIS_DARK, alignment=2)

    st_foot_t  = ps('EDPFootT',  fontName=FX, fontSize=8, leading=11, textColor=GRIS_DARK)
    st_foot_b  = ps('EDPFootB',  fontName=FR, fontSize=7.5, leading=11, textColor=GRIS_MUTED)
    st_foot_c  = ps('EDPFootC',  fontName=FR, fontSize=7.5, leading=11, textColor=GRIS_MUTED, alignment=1)

    # ── 1. ENCABEZADO (Logo / Datos Redimir + Fecha) ─────────
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'redimir_logo_cert.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=44*mm, height=44*mm*(91/558))
    else:
        logo_img = Paragraph('<b><font size=14 color="#006BB8">REDIMIR</font><font size=14 color="#95BF3C">+</font></b>', st_doc_num)

    left_header = [
        logo_img,
        Spacer(1, 2),
        Paragraph('Gestión de Residuos, Asesoría &amp; Logística SpA', st_emp_sub),
        Paragraph(f'N° Documento: <b>{edp.numero_edp}</b>', st_doc_num),
    ]

    fecha_txt = edp.fecha_emision.strftime('%d/%m/%Y')
    estado_display = edp.get_estado_display().upper()
    right_header = [
        Paragraph(f'Fecha: {fecha_txt}', st_date),
        Paragraph(f'Estado: <b>{estado_display}</b>', st_badge),
    ]

    t_head = Table([[left_header, right_header]], colWidths=[310, 200])
    t_head.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    elements.append(t_head)
    elements.append(Spacer(1, 6))

    # Línea divisora verde / negro
    t_line = Table([['', '']], colWidths=[255, 255], rowHeights=[2])
    t_line.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,0), VERDE),
        ('BACKGROUND', (1,0), (1,0), NEGRO),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_line)
    elements.append(Spacer(1, 10))

    # ── 2. INFORMACIÓN DEL CLIENTE ───────────────────────────
    elements.append(Paragraph('INFORMACIÓN DEL CLIENTE', st_sect_t))

    cliente_data = [
        [Paragraph('Razón social:', st_cli_lbl), Paragraph(edp.empresa.nombre, st_cli_val)],
        [Paragraph('RUT:', st_cli_lbl), Paragraph(edp.empresa.rut, st_cli_val)],
        [Paragraph('Dirección:', st_cli_lbl), Paragraph(edp.empresa.direccion or 'Calama / Antofagasta, Chile', st_cli_val)],
        [Paragraph('N° Orden de Compra:', st_cli_lbl), Paragraph(edp.orden_compra or 'N/A', st_cli_val)],
        [Paragraph('Período Facturado:', st_cli_lbl), Paragraph(f"{edp.periodo_inicio.strftime('%d/%m/%Y')} al {edp.periodo_fin.strftime('%d/%m/%Y')}", st_cli_val)],
    ]
    t_cli = Table(cliente_data, colWidths=[120, 390])
    t_cli.setStyle(TableStyle([
        ('TOPPADDING',    (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_cli)
    elements.append(Spacer(1, 10))

    # ── 3. TABLA DE ÍTEMS / SERVICIOS ────────────────────────
    tabla_items = [[
        Paragraph('DESCRIPCIÓN', st_th),
        Paragraph('PRECIO', st_th_r),
        Paragraph('CANTIDAD', st_th_c),
        Paragraph('TOTAL', st_th_r),
    ]]

    detalles = edp.detalles.all()
    if detalles.exists():
        for d in detalles:
            f_txt = d.fechas_texto or (d.fecha_servicio.strftime('%d/%m/%Y') if d.fecha_servicio else "")
            desc_p = [Paragraph(d.descripcion, st_td_desc)]
            if f_txt:
                desc_p.append(Paragraph(f"Fechas: {f_txt}", st_td_sub))

            tarifa_txt = f"$ {int(d.tarifa_unitaria or 0):,}".replace(',', '.')
            cant_txt   = f"{float(d.cantidad or 0):g}"
            subt_txt   = f"$ {int(d.subtotal or 0):,}".replace(',', '.')

            tabla_items.append([
                desc_p,
                Paragraph(tarifa_txt, st_td_r),
                Paragraph(cant_txt, st_td_c),
                Paragraph(subt_txt, st_td_tot),
            ])
    else:
        tabla_items.append([
            Paragraph('Servicios correspondientes al período indicado.', st_td_desc),
            Paragraph(f"$ {int(edp.subtotal_neto or 0):,}".replace(',', '.'), st_td_r),
            Paragraph(f"{edp.total_servicios}", st_td_c),
            Paragraph(f"$ {int(edp.subtotal_neto or 0):,}".replace(',', '.'), st_td_tot),
        ])

    t_items = Table(tabla_items, colWidths=[270, 80, 60, 100])
    t_items_style = [
        ('BACKGROUND',    (0,0), (-1,0), NEGRO),
        ('TOPPADDING',    (0,0), (-1,0), 6),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
    ]
    for r in range(1, len(tabla_items)):
        t_items_style.append(('LINEBELOW', (0, r), (-1, r), 0.5, GRIS_LINEA))

    t_items.setStyle(TableStyle(t_items_style))
    elements.append(t_items)
    elements.append(Spacer(1, 8))

    # ── 4. RESUMEN Y TOTALES (Derecha) ───────────────────────
    subt_val = f"$ {int(edp.subtotal_neto or 0):,}".replace(',', '.')
    iva_val  = f"$ {int(edp.iva or 0):,}".replace(',', '.')
    tot_val  = f"$ {int(edp.total_bruto or 0):,}".replace(',', '.')

    totales_data = [
        ['', Paragraph('Total neto:', st_tot_lbl), Paragraph(subt_val, st_tot_val)],
        ['', Paragraph('IVA (19%):', st_tot_lbl),  Paragraph(iva_val, st_tot_val)],
        ['', Paragraph('<b>TOTAL:</b>', st_g_tot_l), Paragraph(f"<b>{tot_val}</b>", st_g_tot_v)],
    ]
    t_tot = Table(totales_data, colWidths=[290, 100, 120])
    t_tot.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('BACKGROUND',    (1,2), (2,2), GRIS_LINEA),
        ('TOPPADDING',    (1,2), (2,2), 5),
        ('BOTTOMPADDING', (1,2), (2,2), 5),
        ('LEFTPADDING',   (1,2), (2,2), 8),
        ('RIGHTPADDING',  (1,2), (2,2), 8),
    ]))
    elements.append(t_tot)
    elements.append(Spacer(1, 16))

    # ── 5. SECCIÓN INFORMATIVA INFERIOR (3 Columnas) ─────────
    contacto_p = [
        Paragraph('CONTACTO', st_foot_t),
        Spacer(1, 2),
        Paragraph('lplaza@redimir.cl<br/>+56 9 4252 5059<br/>www.redimir.cl', st_foot_b),
    ]

    pago_p = [
        Paragraph('INFORMACIÓN DE PAGO', st_foot_t),
        Spacer(1, 2),
        Paragraph(
            '<b>Cuenta vista:</b> Banco Estado<br/>'
            '<b>Nombre de la cuenta:</b> Redimir SpA<br/>'
            '<b>Número de cuenta:</b> 2171199578<br/>'
            '<b>RUT:</b> 77.854.321-K',
            st_foot_b
        ),
    ]

    firma_p = [
        Paragraph('FIRMA Y TIMBRE', st_foot_t),
        Spacer(1, 14),
        Paragraph('__________________________<br/><b>Leslie Plaza Vargas</b><br/>Directora General &bull; Redimir SpA', st_foot_c),
    ]

    t_foot = Table([[contacto_p, pago_p, firma_p]], colWidths=[150, 200, 160])
    t_foot.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('LINEABOVE',     (0,0), (-1,-1), 0.5, GRIS_LINEA),
        ('TOPPADDING',    (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    elements.append(KeepTogether(t_foot))

    # Construir PDF
    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
