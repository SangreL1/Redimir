import os
import hashlib
import qrcode
from io import BytesIO
from datetime import datetime

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import FileResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.conf import settings
from django.contrib import messages

from .models import Certificado
from apps.servicios.models import Servicio
from apps.empresas.models import Empresa
from apps.usuarios.models import AuditLog

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def generar_pdf_certificado(certificado, request=None):
    """
    Genera el PDF del Certificado de Transporte y Trazabilidad de Residuos
    con ReportLab, logrando exactitud visual 1:1 con el certificado oficial de Redimir.
    """
    # 1. Cargar fuentes Montserrat
    fonts_dir = os.path.join(settings.BASE_DIR, 'static', 'fonts')
    reg_font_path = os.path.join(fonts_dir, 'Montserrat-Regular.ttf')
    bold_font_path = os.path.join(fonts_dir, 'Montserrat-Bold.ttf')
    extrabold_font_path = os.path.join(fonts_dir, 'Montserrat-ExtraBold.ttf')
    light_font_path = os.path.join(fonts_dir, 'Montserrat-Light.ttf')
    semibold_font_path = os.path.join(fonts_dir, 'Montserrat-SemiBold.ttf')

    font_regular = 'Montserrat' if os.path.exists(reg_font_path) else 'Helvetica'
    font_bold = 'Montserrat-Bold' if os.path.exists(bold_font_path) else 'Helvetica-Bold'
    font_extrabold = 'Montserrat-ExtraBold' if os.path.exists(extrabold_font_path) else 'Helvetica-Bold'
    font_light = 'Montserrat-Light' if os.path.exists(light_font_path) else 'Helvetica'
    font_semibold = 'Montserrat-SemiBold' if os.path.exists(semibold_font_path) else 'Helvetica-Bold'

    if font_regular == 'Montserrat':
        try:
            pdfmetrics.registerFont(TTFont('Montserrat', reg_font_path))
            pdfmetrics.registerFont(TTFont('Montserrat-Bold', bold_font_path))
            pdfmetrics.registerFont(TTFont('Montserrat-ExtraBold', extrabold_font_path))
            pdfmetrics.registerFont(TTFont('Montserrat-Light', light_font_path))
            pdfmetrics.registerFont(TTFont('Montserrat-SemiBold', semibold_font_path))
        except Exception:
            pass

    # Colores Corporativos Redimir
    COLOR_AZUL = HexColor("#006BB8")
    COLOR_VERDE = HexColor("#95BF3C")
    COLOR_NEGRO = HexColor("#000000")
    COLOR_GRIS = HexColor("#737373")

    page_width, page_height = A4  # 595.27 x 841.89

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm
    )

    elements = []

    # Estilos tipográficos
    title_style = ParagraphStyle(
        'CertTitle',
        fontName=font_extrabold,
        fontSize=24,
        leading=29,
        textColor=COLOR_NEGRO,
        alignment=1,  # Centrado
        spaceAfter=12
    )

    intro_style = ParagraphStyle(
        'CertIntro',
        fontName=font_regular,
        fontSize=10,
        leading=14.5,
        textColor=COLOR_GRIS,
        alignment=4  # Justificado
    )

    label_style = ParagraphStyle(
        'CertLabel',
        fontName=font_semibold,
        fontSize=10.5,
        leading=14,
        textColor=COLOR_NEGRO
    )

    val_style = ParagraphStyle(
        'CertVal',
        fontName=font_regular,
        fontSize=10.5,
        leading=14,
        textColor=COLOR_NEGRO
    )

    date_style = ParagraphStyle(
        'CertDate',
        fontName=font_light,
        fontSize=11,
        leading=13,
        textColor=COLOR_NEGRO,
        alignment=2  # Derecha
    )

    # ===== 1. ENCABEZADO (Logo Izquierda + Datos Contacto Derecha) =====
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'redimir_logo_cert.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=45 * mm, height=45 * mm * (91 / 558))
    else:
        logo_img = Paragraph(f"<b><font size=14 color='#006BB8'>REDIMIR SpA</font></b>", label_style)

    contact_html = f"""
    <font fontName='{font_regular}' size=8 color='#000000'>
    <b>Pasaje Trans DyF 1643, Calama</b><br/>
    <b>redimir.cl | contacto@redimir.cl</b><br/>
    <b>(56) 9 4252 5059</b>
    </font>
    """
    contact_p = Paragraph(contact_html, ParagraphStyle('HeaderContact', fontName=font_regular, fontSize=8, leading=12, alignment=2))

    t_header = Table([[logo_img, contact_p]], colWidths=[180, 300])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 6))

    # ===== 2. LÍNEA SEPARADORA (Verde mitad + Negro mitad) =====
    t_line = Table([['', '']], colWidths=[240, 240], rowHeights=[2])
    t_line.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_NEGRO),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_line)
    elements.append(Spacer(1, 14))

    # ===== 3. FECHA (Arriba a la derecha en mayúsculas español) =====
    DIAS_ES = {0: 'LUNES', 1: 'MARTES', 2: 'MIÉRCOLES', 3: 'JUEVES', 4: 'VIERNES', 5: 'SÁBADO', 6: 'DOMINGO'}
    MESES_ES_UPPER = {1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO', 6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE', 10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE'}
    MESES_ES_TITLE = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}

    now = timezone.now()
    dia_str = DIAS_ES[now.weekday()]
    mes_str_upper = MESES_ES_UPPER[now.month]
    fecha_texto = f"{dia_str}, {now.day:02d} DE {mes_str_upper} {now.year}"
    elements.append(Paragraph(fecha_texto, date_style))
    elements.append(Spacer(1, 16))

    # ===== 4. TÍTULO PRINCIPAL =====
    elements.append(Paragraph("Certificado de Transporte y<br/>Trazabilidad de Residuos", title_style))
    elements.append(Spacer(1, 18))

    # ===== 5. PÁRRAFO INTRODUCTORIO =====
    p1 = ("Empresa de gestión de residuos <b>Redimir SpA</b> con RUT No. <b>76.781.064-4</b>, certifica que realizó "
          "el traslado a disposición final de residuos, en norma y bajo la resolución de transporte de residuos no peligrosos "
          "<b>N° 1618</b> de la <b>SEREMI DE SALUD DE ANTOFAGASTA</b>.")
    elements.append(Paragraph(p1, intro_style))
    elements.append(Spacer(1, 12))

    if hasattr(certificado, 'periodo_inicio') and certificado.periodo_inicio:
        p_ini = certificado.periodo_inicio
        if isinstance(p_ini, str):
            try:
                p_ini = datetime.strptime(p_ini, "%Y-%m-%d")
            except Exception:
                p_ini = now
        p_mes = MESES_ES_TITLE[p_ini.month]
        p_anio = p_ini.year
    else:
        p_mes = MESES_ES_TITLE[now.month]
        p_anio = now.year

    p2 = f"En el mes de <b>{p_mes}</b> del <b>{p_anio}</b> se han trasladado los residuos no peligrosos desde:"
    elements.append(Paragraph(p2, intro_style))
    elements.append(Spacer(1, 18))

    # ===== 6. SECCIÓN DE DATOS (Dos columnas) =====
    empresa = certificado.empresa
    cliente_nombre = empresa.nombre
    cliente_direccion = getattr(empresa, 'direccion', '') or ''
    cliente_ciudad = getattr(empresa, 'comuna', '') or getattr(empresa, 'ciudad', '') or 'Calama'

    if cliente_direccion and cliente_ciudad and cliente_ciudad.lower() not in cliente_direccion.lower():
        dir_completa = f"{cliente_direccion}, {cliente_ciudad}"
    else:
        dir_completa = cliente_direccion or "Calama, Región de Antofagasta"

    # Formatear desglose de residuos
    desglose = certificado.desglose_por_tipo or {}
    residuos_lines = []
    # Tipos de residuos que se cuentan como retiros, no en Kg
    TIPOS_RETIRO = ('escombros', 'rescon', 'otros residuos')
    if desglose:
        for tipo, cant in desglose.items():
            if isinstance(cant, (int, float)):
                cant_fmt = f"{cant:g}".replace('.', ',')
                tipo_lower = tipo.lower()
                if any(t in tipo_lower for t in TIPOS_RETIRO) or 'm3' in tipo_lower:
                    residuos_lines.append(f"{tipo}: {cant_fmt} Retiros")
                else:
                    residuos_lines.append(f"{tipo}: {cant_fmt} Kg.")
            else:
                residuos_lines.append(f"{tipo}: {cant}")
    else:
        total_rec = float(certificado.total_reciclables_kg or 0)
        total_rsd = float(certificado.total_rsd_kg or 0)
        if total_rec > 0:
            residuos_lines.append(f"Materiales Reciclables: {total_rec:g}".replace('.', ',') + " Kg.")
        if total_rsd > 0:
            residuos_lines.append(f"Residuos Sólidos Domésticos: {total_rsd:g}".replace('.', ',') + " Kg.")

    residuos_html = "<br/>".join(residuos_lines) if residuos_lines else "Residuos no peligrosos varios"

    total_kg_val = float(certificado.total_reciclables_kg or 0) + float(certificado.total_rsd_kg or 0)
    if total_kg_val > 0 and certificado.total_escombros > 0:
        total_kg_str = f"{total_kg_val:g} Kg. + {certificado.total_escombros} Retiro(s) Escombros".replace('.', ',')
    elif total_kg_val > 0:
        total_kg_str = f"{total_kg_val:g}".replace('.', ',') + " Kg."
    else:
        total_kg_str = f"{certificado.total_escombros} Retiro(s)"

    # Destino oficial fijo del certificado Redimir
    destino_str = "Recinort, Recipet y Redimir."

    grid_data = [
        [Paragraph('Institución:', label_style), Paragraph(cliente_nombre, val_style)],
        [Paragraph('Dirección:', label_style), Paragraph(dir_completa, val_style)],
        [Paragraph('Tipos de Residuos:', label_style), Paragraph(residuos_html, val_style)],
        [Paragraph('Cantidad:', label_style), Paragraph(total_kg_str, val_style)],
        [Paragraph('Destino:', label_style), Paragraph(destino_str, val_style)],
    ]

    t_grid = Table(grid_data, colWidths=[140, 340])
    t_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_grid)
    elements.append(Spacer(1, 20))

    # ===== 7. PÁRRAFO FINAL Y UBICACIÓN =====
    p3 = "Los residuos antes nombrados cumplieron con la trazabilidad sustentable, siendo derivados a las plantas de reciclaje antes mencionadas."
    elements.append(Paragraph(p3, intro_style))
    elements.append(Spacer(1, 20))

    p4 = "Calama, Región de Antofagasta, Chile."
    elements.append(Paragraph(p4, intro_style))
    elements.append(Spacer(1, 30))

    # ===== 8. FIRMA Y VERIFICACIÓN QR =====
    firma_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'firma_directora.png')
    if os.path.exists(firma_path):
        try:
            from PIL import Image as PILImage
            im_sig = PILImage.open(firma_path)
            sig_w = 45 * mm
            sig_h = sig_w * (im_sig.height / im_sig.width)
            firma_img = Image(firma_path, width=sig_w, height=sig_h)
        except Exception:
            firma_img = Spacer(1, 15)
    else:
        firma_img = Spacer(1, 15)

    resp_nombre = getattr(certificado, 'responsable_nombre', None) or "Leslie Plaza Vargas"
    resp_cargo = getattr(certificado, 'responsable_cargo', None) or "DIRECTORA GENERAL"

    sig_html = f"""
    <font fontName='{font_bold}' size=12 color='#000000'>{resp_nombre}</font><br/>
    <font fontName='{font_regular}' size=9.5 color='#737373'>{resp_cargo}</font><br/>
    <font fontName='{font_regular}' size=9.5 color='#737373'>REDIMIR SpA • Gestión de Residuos</font>
    """
    sig_p = Paragraph(sig_html, ParagraphStyle('SigP', leading=13))

    left_block = [firma_img, Spacer(1, 4), sig_p]

    # Código QR
    if request:
        qr_url = request.build_absolute_uri(f"/verificar/{certificado.codigo_certificado}/")
    else:
        qr_url = f"https://redimir.cl/verificar/{certificado.codigo_certificado}/"

    certificado.qr_certificado = qr_url

    qr_img_obj = qrcode.make(qr_url)
    qr_buf = BytesIO()
    qr_img_obj.save(qr_buf, 'PNG')
    qr_buf.seek(0)

    img_qr = Image(qr_buf, width=18 * mm, height=18 * mm)
    icon_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'cert_icon_bottom.png')
    if os.path.exists(icon_path):
        icon_img = Image(icon_path, width=16 * mm, height=16 * mm * (334 / 359))
    else:
        icon_img = Spacer(1, 10)

    qr_text = f"<font fontName='{font_regular}' size=7.5 color='#737373'><b>FOLIO: {certificado.codigo_certificado}</b><br/>VERIFICADO ONLINE<br/>Escanea para autenticidad</font>"
    qr_p = Paragraph(qr_text, ParagraphStyle('QrP', leading=9.5, alignment=1))

    qr_table = Table([[icon_img, img_qr], ['', qr_p]], colWidths=[22 * mm, 22 * mm])
    qr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('SPAN', (1, 1), (1, 1)),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    t_footer = Table([[left_block, qr_table]], colWidths=[330, 150])
    t_footer.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(KeepTogether(t_footer))

    # Decoración de esquina canvas
    def draw_canvas(canvas, document):
        canvas.saveState()
        wave_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'cert_corner_wave.png')
        if os.path.exists(wave_path):
            try:
                from PIL import Image as PILImage
                im_w = PILImage.open(wave_path)
                w = 70 * mm
                h = w * (im_w.height / im_w.width)
                canvas.drawImage(wave_path, page_width - w, 0, width=w, height=h, mask='auto')
            except Exception:
                pass
        canvas.restoreState()

    doc.build(elements, onFirstPage=draw_canvas, onLaterPages=draw_canvas)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Cálculo Hash SHA-256
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
    certificado.hash_sha256 = pdf_hash
    certificado.estado = 'vigente'

    from django.core.files.base import ContentFile
    filename = f"Certificado_{certificado.codigo_certificado}.pdf"
    certificado.archivo_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    certificado.save()

    return certificado.archivo_pdf.path


@login_required
def descargar_certificado(request, certificado_id):
    """Generar y descargar PDF del certificado con control de seguridad"""
    try:
        certificado = Certificado.objects.get(id=certificado_id)

        # Control de permisos (Admin/Gerencia/Staff o usuario de la empresa correspondiente)
        user = request.user
        es_admin_o_staff = (
            getattr(user, 'es_admin', lambda: False)() or
            user.is_superuser or
            user.is_staff or
            getattr(user, 'rol', '') in ('admin', 'gerencia', 'superadmin')
        )
        es_empresa_duena = getattr(user, 'empresa', None) == certificado.empresa

        if not (es_admin_o_staff or es_empresa_duena):
            return HttpResponseForbidden("No tiene permisos para acceder a este certificado.")

        # Si no existe archivo físico en disco, generarlo dinámicamente
        if not certificado.archivo_pdf or not os.path.exists(certificado.archivo_pdf.path):
            generar_pdf_certificado(certificado, request=request)

        pdf_path = certificado.archivo_pdf.path

        response = FileResponse(open(pdf_path, 'rb'), content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Certificado_{certificado.codigo_certificado}.pdf"'
        return response

    except Certificado.DoesNotExist:
        return HttpResponseNotFound("El certificado solicitado no existe.")


@method_decorator(login_required, name='dispatch')
class ListaCertificadosView(View):
    template_name = 'certificados/lista.html'

    def get(self, request):
        user = request.user
        es_admin_o_staff = (
            getattr(user, 'es_admin', lambda: False)() or
            user.is_superuser or
            user.is_staff or
            getattr(user, 'rol', '') in ('admin', 'gerencia', 'superadmin')
        )
        if es_admin_o_staff:
            certificados = Certificado.objects.all().order_by('-fecha_generacion')
        elif getattr(user, 'empresa', None):
            certificados = Certificado.objects.filter(empresa=user.empresa).order_by('-fecha_generacion')
        else:
            certificados = Certificado.objects.none()

        return render(request, self.template_name, {'certificados': certificados})


@method_decorator(login_required, name='dispatch')
class GeneradorPageView(View):
    template_name = 'certificados/generador.html'

    def get(self, request):
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        return render(request, self.template_name, {'empresas': empresas})

    def post(self, request):
        empresa_id = request.POST.get('empresa_id')
        inicio = request.POST.get('inicio')
        fin = request.POST.get('fin')
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        error = None
        certificado = None

        if not empresa_id or not inicio or not fin:
            error = 'Todos los campos son requeridos.'
        else:
            try:
                empresa = Empresa.objects.get(id=empresa_id)

                from django.db.models import Q
                from apps.lotes.models import Lote
                from apps.empresas.models import SolicitudRecoleccion

                # ── 1. Servicios validados (modelo nuevo) ──────────────────
                servicios = Servicio.objects.filter(
                    empresa=empresa,
                    estado__in=['validado', 'documento_emitido', 'cerrado'],
                ).filter(
                    Q(fecha_retiro_real__date__range=[inicio, fin]) |
                    Q(fecha_retiro_real__isnull=True, fecha_validacion__date__range=[inicio, fin])
                )

                # ── 2. Lotes (modelo legado — donde viven los datos reales) ─
                lotes = Lote.objects.filter(
                    empresa_origen=empresa,
                    fecha_recoleccion__date__range=[inicio, fin]
                )

                # ── 3. Solicitudes de Recolección (modelo legado) ──────────
                solicitudes = SolicitudRecoleccion.objects.filter(
                    empresa=empresa,
                    estado__in=['pendiente', 'asignada', 'completada'],
                    fecha_solicitada__date__range=[inicio, fin]
                )

                # Si no hay NADA de ninguno de los tres, error
                if not servicios.exists() and not lotes.exists() and not solicitudes.exists():
                    error = 'No hay retiros registrados para esta empresa en el período indicado.'
                else:
                    rsd_kg = 0
                    escombros_total = 0
                    reciclables_kg = 0
                    desglose = {}

                    # Procesar Servicios
                    for s in servicios:
                        reg = s.get_registro()
                        if s.modulo == 'rsd' and reg:
                            cant = float(reg.cantidad_kg) if reg.cantidad_kg else 0.0
                            rsd_kg += reg.cantidad_kg or 0
                            desglose['RSD / Basura General'] = round(desglose.get('RSD / Basura General', 0.0) + cant, 2)
                        elif s.modulo == 'escombros' and reg:
                            escombros_total += 1
                            cant = float(reg.cantidad) if reg.cantidad else 0.0
                            key = f"Escombros ({reg.get_unidad_display() if hasattr(reg, 'get_unidad_display') else 'm3'})"
                            desglose[key] = round(desglose.get(key, 0.0) + cant, 2)
                        elif s.modulo == 'reciclables' and reg:
                            cant = float(reg.cantidad_kg) if reg.cantidad_kg else 0.0
                            reciclables_kg += reg.cantidad_kg or 0
                            key = f"Reciclables - {reg.get_material_display() if hasattr(reg, 'get_material_display') else 'General'}"
                            desglose[key] = round(desglose.get(key, 0.0) + cant, 2)

                    # Procesar Lotes (modelo legado)
                    MAPA_TIPO_LOTE = {
                        'basura':    ('rsd',         'RSD / Basura General'),
                        'escombros': ('escombros',   'Escombros / RESCON'),
                        'plastico':  ('reciclables', 'Reciclables - Plástico'),
                        'metal':     ('reciclables', 'Reciclables - Metal'),
                        'papel':     ('reciclables', 'Reciclables - Papel/Cartón'),
                        'vidrio':    ('reciclables', 'Reciclables - Vidrio'),
                        'organico':  ('reciclables', 'Reciclables - Orgánico'),
                        'mixto':     ('reciclables', 'Reciclables - Mixto'),
                    }
                    for lote in lotes:
                        kg = float(lote.cantidad_kg) if lote.cantidad_kg else 0.0
                        modulo_lote, label = MAPA_TIPO_LOTE.get(lote.tipo_residuo, ('reciclables', f'Reciclables - {lote.get_tipo_residuo_display()}'))
                        if modulo_lote == 'rsd':
                            rsd_kg += lote.cantidad_kg or 0
                        elif modulo_lote == 'escombros':
                            escombros_total += 1
                        else:
                            reciclables_kg += lote.cantidad_kg or 0
                        desglose[label] = round(desglose.get(label, 0.0) + kg, 2)

                    # Procesar Solicitudes de Recolección (modelo legado)
                    MAPA_MODULO_SOL = {
                        'rsd':         ('rsd',         'RSD / Basura General'),
                        'escombros':   ('escombros',   'Escombros / RESCON'),
                        'reciclables': ('reciclables', 'Reciclables - General'),
                        'otros':       ('reciclables', 'Otros Residuos'),
                    }
                    MAPA_MATERIAL_SOL = {
                        'carton':    'Reciclables - Cartón/Papel',
                        'pet':       'Reciclables - Botellas PET',
                        'vidrio':    'Reciclables - Vidrio',
                        'latas':     'Reciclables - Latas',
                        'film':      'Reciclables - Film LDPE',
                        'plastico':  'Reciclables - Plástico',
                        'escombros': 'Escombros / RESCON',
                        'rsd':       'RSD / Basura General',
                        'mixto':     'Reciclables - Mixto',
                        'otros':     'Otros Residuos',
                    }
                    for sol in solicitudes:
                        # Usar tipo_material si está disponible, sino el módulo
                        label_sol = MAPA_MATERIAL_SOL.get(
                            sol.tipo_material,
                            MAPA_MODULO_SOL.get(sol.modulo, ('reciclables', 'Reciclables - General'))[1]
                        )
                        modulo_sol = MAPA_MODULO_SOL.get(sol.modulo, ('reciclables', ''))[0]
                        cant_sol = float(sol.cantidad_estimada) if sol.cantidad_estimada else 0.0
                        if modulo_sol == 'rsd':
                            rsd_kg += sol.cantidad_estimada or 0
                        elif modulo_sol == 'escombros':
                            escombros_total += 1
                        else:
                            reciclables_kg += sol.cantidad_estimada or 0
                        # Solo sumar kg si la unidad es peso; para escombros/otros contar como retiro
                        if sol.unidad_medida in ('kg', 'Kg', 'KG'):
                            desglose[label_sol] = round(desglose.get(label_sol, 0.0) + cant_sol, 2)
                        else:
                            # Contar como 1 retiro si no es en kg
                            prev = desglose.get(label_sol, 0.0)
                            desglose[label_sol] = round(prev + (cant_sol if cant_sol > 0 else 1.0), 2)

                    total_registros = servicios.count() + lotes.count() + solicitudes.count()

                    certificado = Certificado.objects.create(
                        empresa=empresa,
                        periodo_inicio=inicio,
                        periodo_fin=fin,
                        total_rsd_kg=rsd_kg,
                        total_escombros=escombros_total,
                        total_reciclables_kg=reciclables_kg,
                        numero_servicios=total_registros,
                        desglose_por_tipo=desglose,
                        generado_por=request.user
                    )
                    certificado.servicios.set(servicios)

                    # Generar PDF con ReportLab
                    generar_pdf_certificado(certificado, request=request)

                    # Registro de auditoría
                    AuditLog.registrar(
                        usuario=request.user,
                        accion='emision_doc',
                        modelo='Certificado',
                        registro_id=certificado.codigo_certificado,
                        campo='archivo_pdf',
                        valor_anterior='',
                        valor_nuevo=f"SHA256:{certificado.hash_sha256[:16]}...",
                        detalles=f"Certificado {certificado.codigo_certificado} emitido para {empresa.nombre} del {inicio} al {fin}.",
                        ip=request.META.get('REMOTE_ADDR')
                    )

                    messages.success(request, f"Certificado {certificado.codigo_certificado} generado exitosamente con el formato oficial Redimir.")

            except Empresa.DoesNotExist:
                error = 'Empresa no encontrada.'
            except Exception as e:
                error = f'Error al generar certificado: {e}'

        return render(request, self.template_name, {
            'empresas': empresas,
            'error': error,
            'certificado': certificado,
        })


class VerificarCertificadoView(View):
    """
    Vista pública para verificación de certificados escaneando el código QR.
    """
    template_name = 'certificados/verificar.html'

    def get(self, request, codigo):
        try:
            certificado = Certificado.objects.get(codigo_certificado=codigo)
            return render(request, self.template_name, {
                'certificado': certificado,
                'error': None
            })
        except Certificado.DoesNotExist:
            return render(request, self.template_name, {
                'certificado': None,
                'error': f'El código o folio "{codigo}" no corresponde a ningún certificado válido en el sistema Redimir.'
            })
