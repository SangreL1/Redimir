import os
import hashlib
import qrcode
from io import BytesIO
from datetime import datetime

from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import FileResponse, HttpResponseForbidden, HttpResponseNotFound, HttpResponse, JsonResponse
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
                from apps.empresas.models import SolicitudRecoleccion

                # ── 1. Servicios validados (modelo nuevo) ──────────────────
                servicios = Servicio.objects.filter(
                    empresa=empresa,
                    estado__in=['validado', 'documento_emitido', 'cerrado'],
                ).filter(
                    Q(fecha_retiro_real__date__range=[inicio, fin]) |
                    Q(fecha_retiro_real__isnull=True, fecha_validacion__date__range=[inicio, fin])
                )

                # ── 2. Solicitudes de Recolección (modelo legado) ──────────
                solicitudes = SolicitudRecoleccion.objects.filter(
                    empresa=empresa,
                    estado__in=['pendiente', 'asignada', 'completada'],
                    fecha_solicitada__date__range=[inicio, fin]
                )

                # Si no hay NADA de ninguno de los dos, error
                if not servicios.exists() and not solicitudes.exists():
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

                    total_registros = servicios.count() + solicitudes.count()

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


# ============================================================
# CERTIFICADO DE ECO-EQUIVALENCIA
# ============================================================

# Factores de eco-equivalencia por material (unidad: por kg reciclado)
ECO_FACTORES = {
    'pellon':    {'energia': 3.5,  'co2': 1.1,  'agua': 50,  'arboles': 1/45, 'combustible': 0.15},
    'carton':    {'energia': 3.5,  'co2': 1.1,  'agua': 50,  'arboles': 1/45, 'combustible': 0.15},
    'papel':     {'energia': 3.5,  'co2': 1.1,  'agua': 50,  'arboles': 1/45, 'combustible': 0.15},
    'plastico':  {'energia': 5.8,  'co2': 2.0,  'agua': 30,  'arboles': 0,    'combustible': 0.30},
    'aluminio':  {'energia': 14.0, 'co2': 9.0,  'agua': 40,  'arboles': 0,    'combustible': 0.50},
    'vidrio':    {'energia': 0.8,  'co2': 0.3,  'agua': 10,  'arboles': 0,    'combustible': 0.05},
    'film':      {'energia': 5.8,  'co2': 2.0,  'agua': 30,  'arboles': 0,    'combustible': 0.30},
    'carretes':  {'energia': 3.5,  'co2': 1.1,  'agua': 50,  'arboles': 0,    'combustible': 0.15},
    'sunchos':   {'energia': 5.8,  'co2': 2.0,  'agua': 30,  'arboles': 0,    'combustible': 0.30},
}

# Mapeo de nombres de tipo_material de BD a clave de ECO_FACTORES
MATERIAL_KEYS = {
    'pellon':   'pellon',
    'carton':   'carton',
    'papel':    'papel',
    'pet':      'plastico',
    'plastico': 'plastico',
    'latas':    'aluminio',
    'aluminio': 'aluminio',
    'vidrio':   'vidrio',
    'film':     'film',
    'carretes': 'carretes',
    'sunchos':  'sunchos',
}

# Materiales que se muestran en el certificado (en orden)
MATERIALES_CERT = [
    ('pellon',   'Pellón'),
    ('carton',   'Cartón'),
    ('papel',    'Papel'),
    ('plastico', 'Botellas Plásticas'),
    ('aluminio', 'Latas de Aluminio'),
    ('vidrio',   'Botellas de Vidrio'),
    ('film',     'Film LDPE'),
    ('carretes', 'Carretes'),
    ('sunchos',  'Sunchos'),
]


def calcular_eco_beneficios(materiales_kg):
    """Calcula los beneficios ambientales totales dados kg por tipo de material.
    materiales_kg = {'carton': 101, 'plastico': 20, ...}
    """
    energia = co2 = agua = arboles = combustible = 0.0
    for mat_key, kg in materiales_kg.items():
        factores = ECO_FACTORES.get(mat_key, {})
        if factores and kg:
            kg = float(kg)
            energia    += kg * factores['energia']
            co2        += kg * factores['co2']
            agua       += kg * factores['agua']
            arboles    += kg * factores['arboles']
            combustible += kg * factores['combustible']
    return {
        'energia':     round(energia),
        'co2':         round(co2),
        'agua':        round(agua),
        'arboles':     round(arboles),
        'combustible': round(combustible),
    }


def generar_pdf_eco_equivalencia(datos, request=None):
    """
    Genera el PDF del Certificado de Eco-Equivalencia — diseño idéntico al certificado oficial.
    datos = {
        'empresa': Empresa instance,
        'mes_nombre': 'enero',
        'anio': 2022,
        'materiales_kg': {'carton': 101, 'plastico': 20, ...},
        'codigo': 'ECO-001',
        'responsable_nombre': 'Leslie Plaza Vargas',
        'responsable_cargo': 'DIRECTORA GENERAL',
    }
    Retorna bytes del PDF.
    """
    # ── Fuentes ──────────────────────────────────────────────
    fonts_dir  = os.path.join(settings.BASE_DIR, 'static', 'fonts')
    reg_path   = os.path.join(fonts_dir, 'Montserrat-Regular.ttf')
    bold_path  = os.path.join(fonts_dir, 'Montserrat-Bold.ttf')
    xbold_path = os.path.join(fonts_dir, 'Montserrat-ExtraBold.ttf')
    light_path = os.path.join(fonts_dir, 'Montserrat-Light.ttf')
    semi_path  = os.path.join(fonts_dir, 'Montserrat-SemiBold.ttf')

    FR = 'Montserrat'           if os.path.exists(reg_path)   else 'Helvetica'
    FB = 'Montserrat-Bold'      if os.path.exists(bold_path)  else 'Helvetica-Bold'
    FX = 'Montserrat-ExtraBold' if os.path.exists(xbold_path) else 'Helvetica-Bold'
    FL = 'Montserrat-Light'     if os.path.exists(light_path) else 'Helvetica'
    FS = 'Montserrat-SemiBold'  if os.path.exists(semi_path)  else 'Helvetica-Bold'

    if FR == 'Montserrat':
        try:
            pdfmetrics.registerFont(TTFont('Montserrat',           reg_path))
            pdfmetrics.registerFont(TTFont('Montserrat-Bold',      bold_path))
            pdfmetrics.registerFont(TTFont('Montserrat-ExtraBold', xbold_path))
            pdfmetrics.registerFont(TTFont('Montserrat-Light',     light_path))
            pdfmetrics.registerFont(TTFont('Montserrat-SemiBold',  semi_path))
        except Exception:
            pass

    # ── Colores ───────────────────────────────────────────────
    AZUL   = HexColor('#006BB8')
    VERDE  = HexColor('#95BF3C')
    NEGRO  = HexColor('#000000')
    GRIS   = HexColor('#737373')
    GRIS_B = HexColor('#DDDDDD')

    page_width, page_height = A4
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=22*mm, rightMargin=22*mm,
        topMargin=18*mm, bottomMargin=18*mm
    )
    els = []

    def ps(name, **kw):
        return ParagraphStyle(name, **kw)

    # Estilos de texto
    st_date  = ps('EcoDate',  fontName=FL, fontSize=10, leading=13, textColor=NEGRO, alignment=2)
    st_title = ps('EcoTitle', fontName=FX, fontSize=20, leading=24, textColor=NEGRO, alignment=1, spaceAfter=4)
    st_intro = ps('EcoIntro', fontName=FR, fontSize=10, leading=14, textColor=GRIS,  alignment=0)
    st_head  = ps('EcoHead',  fontName=FB, fontSize=9.5,leading=12, textColor=NEGRO, alignment=0)
    st_label = ps('EcoLabel', fontName=FS, fontSize=10, leading=14, textColor=NEGRO, alignment=0)
    st_val   = ps('EcoVal',   fontName=FR, fontSize=10, leading=14, textColor=NEGRO, alignment=0)
    st_tot   = ps('EcoTot',   fontName=FB, fontSize=10, leading=14, textColor=NEGRO, alignment=0)

    # ── 1. ENCABEZADO (Logo + Contacto) ───────────────────────
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'redimir_logo_cert.png')
    if os.path.exists(logo_path):
        logo_img = Image(logo_path, width=42*mm, height=42*mm*(91/558))
    else:
        logo_img = Paragraph('<b><font size=14 color="#006BB8">REDIMIR</font></b>', st_label)

    contact_html = (
        f"<font fontName=\'{FR}\' size=8>"
        "<b>(56) 9 4252 5059</b><br/>"
        "<b>www.redimir.cl | contacto@redimir.cl</b><br/>"
        "<b>Pasaje Trans DyF 1643, Calama</b>"
        "</font>"
    )
    contact_p = Paragraph(contact_html, ps('EcoContact', fontName=FR, fontSize=8, leading=11, alignment=2))

    t_header = Table([[logo_img, contact_p]], colWidths=[180, 295])
    t_header.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',         (0,0), (0,0),   'LEFT'),
        ('ALIGN',         (1,0), (1,0),   'RIGHT'),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    els.append(t_header)
    els.append(Spacer(1, 3))

    # ── 2. LÍNEA DIVISORA (Verde | Negro) ────────────────────
    t_line = Table([['', '']], colWidths=[237, 238], rowHeights=[2])
    t_line.setStyle(TableStyle([
        ('BACKGROUND',    (0,0), (0,0), VERDE),
        ('BACKGROUND',    (1,0), (1,0), NEGRO),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
    ]))
    els.append(t_line)
    els.append(Spacer(1, 7))

    # ── 3. FECHA (derecha) ────────────────────────────────────
    DIAS_ES  = {0:'LUNES',1:'MARTES',2:'MIÉRCOLES',3:'JUEVES',4:'VIERNES',5:'SÁBADO',6:'DOMINGO'}
    MESES_UP = {1:'ENERO',2:'FEBRERO',3:'MARZO',4:'ABRIL',5:'MAYO',6:'JUNIO',
                7:'JULIO',8:'AGOSTO',9:'SEPTIEMBRE',10:'OCTUBRE',11:'NOVIEMBRE',12:'DICIEMBRE'}
    now = timezone.now()
    fecha_txt = f"{DIAS_ES[now.weekday()]}, {now.day:02d} DE {MESES_UP[now.month]} {now.year}"
    els.append(Paragraph(fecha_txt, st_date))
    els.append(Spacer(1, 8))

    # ── 4. TÍTULO ─────────────────────────────────────────────
    els.append(Paragraph('Certificado de Eco-Equivalencia', st_title))
    els.append(Spacer(1, 8))

    # ── 5. PÁRRAFO INTRODUCTORIO ──────────────────────────────
    empresa    = datos['empresa']
    mes_titulo = datos.get('mes_nombre', 'el mes').capitalize()
    anio       = datos.get('anio', now.year)
    ciudad     = getattr(empresa, 'ciudad', '') or getattr(empresa, 'comuna', '') or ''
    nombre_emp = empresa.nombre + (f' {ciudad}' if ciudad else '')

    intro_txt = (
        f"Informe de Gestión de Residuos y Eco-Equivalencia del mes de "
        f"<b>{mes_titulo}</b> para la empresa <b>{nombre_emp}</b>."
    )
    els.append(Paragraph(intro_txt, st_intro))
    els.append(Spacer(1, 8))

    # ── 6. TABLA DE RESIDUOS (sin bordes, minimalista) ───────
    materiales_kg = datos.get('materiales_kg', {})
    total_kg = sum(float(v) for v in materiales_kg.values() if v)

    tabla_data = [[
        Paragraph('RESIDUOS', st_head),
        Paragraph('CANTIDAD', st_head),
    ]]
    for mat_key, mat_label in MATERIALES_CERT:
        kg_val = float(materiales_kg.get(mat_key, 0))
        kg_str = f"{kg_val:g} kg." if kg_val else "0 kg."
        tabla_data.append([
            Paragraph(f"{mat_label}:", st_label),
            Paragraph(kg_str, st_val),
        ])

    total_str = f"{total_kg:g} kg." if total_kg else "0 kg."
    tabla_data.append([
        Paragraph('TOTAL:', st_tot),
        Paragraph(f"<b>{total_str}</b>", st_tot),
    ])

    n_filas = len(tabla_data)
    t_residuos = Table(tabla_data, colWidths=[230, 120])
    t_residuos.setStyle(TableStyle([
        ('LINEBELOW',     (0,0), (-1,0), 0.5, GRIS_B),
        ('LINEABOVE',     (0,n_filas-1), (-1,n_filas-1), 0.5, GRIS_B),
        ('TOPPADDING',    (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 8),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
    ]))
    els.append(t_residuos)
    els.append(Spacer(1, 8))

    # ── 7. ENLACE A BENEFICIOS ────────────────────────────────
    els.append(Paragraph(
        'De esta forma, generamos los siguientes beneficios ambientales:',
        st_intro
    ))
    els.append(Spacer(1, 6))

    # ── 8. TARJETAS DE BENEFICIOS AMBIENTALES ────────────────
    beneficios = calcular_eco_beneficios(materiales_kg)
    icons_dir  = os.path.join(settings.BASE_DIR, 'static', 'img', 'eco_icons')

    def fmt_num(n):
        s = f"{n:,.0f}"
        return s.replace(',', '.')

    comb_val  = f"{fmt_num(beneficios['combustible'])} L"
    energ_val = f"{fmt_num(beneficios['energia'])} kW"
    co2_val   = f"{fmt_num(beneficios['co2'])} Kg"
    agua_val  = f"{fmt_num(beneficios['agua'])} L"
    arb_val   = str(max(1, int(beneficios['arboles']))) if total_kg > 0 else '0'

    ICON_SIZE = 13 * mm
    CARD_W    = 148

    def make_icon_img(filename):
        path = os.path.join(icons_dir, filename)
        if os.path.exists(path):
            try:
                return Image(path, width=ICON_SIZE, height=ICON_SIZE)
            except Exception:
                return None
        return None

    def beneficio_card(icon_file, valor_txt, label1, label2=''):
        uid = icon_file.replace('.', '_')
        st_val_b = ps(f'BVal{uid}', fontName=FB, fontSize=12, leading=15,
                      textColor=AZUL, alignment=1)
        st_lbl_b = ps(f'BLbl{uid}', fontName=FR, fontSize=7.5, leading=10,
                      textColor=GRIS, alignment=1)
        ico = make_icon_img(icon_file)
        items = []
        if ico:
            t_ico = Table([[ico]], colWidths=[CARD_W - 16])
            t_ico.setStyle(TableStyle([
                ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
                ('TOPPADDING',    (0,0), (-1,-1), 0),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
                ('LEFTPADDING',   (0,0), (-1,-1), 0),
                ('RIGHTPADDING',  (0,0), (-1,-1), 0),
            ]))
            items.append(t_ico)
        items.append(Paragraph(f"<b>{valor_txt}</b>", st_val_b))
        items.append(Spacer(1, 1))
        items.append(Paragraph(label1, st_lbl_b))
        if label2:
            items.append(Paragraph(label2, st_lbl_b))
        return items

    c1 = beneficio_card('combustible.jpg', comb_val,  'de ahorro en',    'combustibles fósiles')
    c2 = beneficio_card('energia.jpg',     energ_val, 'de ahorro en',    'energía eléctrica')
    c3 = beneficio_card('co2.jpg',         co2_val,   'de reducción en', 'emisiones de CO\u2082')
    c4 = beneficio_card('agua.jpg',        agua_val,  'de ahorro',       'en agua')
    c5 = beneficio_card('arboles.jpg',     arb_val,   'árboles adultos', 'no talados')

    card_style = [
        ('VALIGN',        (0,0), (-1,-1), 'TOP'),
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('TOPPADDING',    (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
        ('RIGHTPADDING',  (0,0), (-1,-1), 6),
    ]

    t_b1 = Table([[c1, c2, c3]], colWidths=[CARD_W, CARD_W, CARD_W])
    t_b1.setStyle(TableStyle(card_style + [
        ('BOX', (0,0), (0,0), 0.6, GRIS_B),
        ('BOX', (1,0), (1,0), 0.6, GRIS_B),
        ('BOX', (2,0), (2,0), 0.6, GRIS_B),
    ]))
    els.append(t_b1)
    els.append(Spacer(1, 4))

    t_b2 = Table([[c4, c5, '']], colWidths=[CARD_W, CARD_W, CARD_W])
    t_b2.setStyle(TableStyle(card_style + [
        ('BOX', (0,0), (0,0), 0.6, GRIS_B),
        ('BOX', (1,0), (1,0), 0.6, GRIS_B),
    ]))
    els.append(t_b2)
    els.append(Spacer(1, 12))

    # ── 9. FIRMA ─────────────────────────────────────────────
    resp_nombre = datos.get('responsable_nombre', 'Leslie Plaza Vargas')
    resp_cargo  = datos.get('responsable_cargo',  'DIRECTORA GENERAL')

    firma_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'firma_directora.png')
    if os.path.exists(firma_path):
        try:
            from PIL import Image as PILImage
            im_s = PILImage.open(firma_path)
            sig_w = 42 * mm
            sig_h = sig_w * (im_s.height / im_s.width)
            firma_img = Image(firma_path, width=sig_w, height=sig_h)
        except Exception:
            firma_img = Spacer(1, 20)
    else:
        firma_img = Spacer(1, 20)

    # La imagen firma_directora.png ya es el nombre en negrita — NO repetirlo
    sig_html = (
        f"<font fontName=\'{FR}\' size=9 color=\'#737373\'>{resp_cargo}</font><br/>"
        f"<font fontName=\'{FR}\' size=9 color=\'#737373\'>REDIMIR SpA \u2022 Gestión de Residuos</font>"
    )
    sig_p  = Paragraph(sig_html, ps('SigEco', leading=14))
    left_b = [firma_img, Spacer(1, 4), sig_p]

    logo_dec_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'cert_icon_bottom.png')
    if os.path.exists(logo_dec_path):
        logo_dec = Image(logo_dec_path, width=28*mm, height=28*mm*(334/359))
    else:
        logo_dec = Paragraph(
            f"<font fontName=\'{FB}\' size=22 color=\'#006BB8\'>R</font>",
            ps('RDec', alignment=1)
        )

    t_foot = Table([[left_b, logo_dec]], colWidths=[380, 95])
    t_foot.setStyle(TableStyle([
        ('VALIGN',        (0,0), (-1,-1), 'BOTTOM'),
        ('ALIGN',         (1,0), (1,0),   'RIGHT'),
        ('LEFTPADDING',   (0,0), (-1,-1), 0),
        ('RIGHTPADDING',  (0,0), (-1,-1), 0),
        ('TOPPADDING',    (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    els.append(KeepTogether(t_foot))

    # ── 10. DECORACIÓN CANVAS (ola azul esquina inferior) ────
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

    doc.build(els, onFirstPage=draw_canvas, onLaterPages=draw_canvas)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes

@login_required
def api_datos_empresa_mes(request):
    """
    Endpoint AJAX: retorna los kg de reciclables de una empresa en un mes.
    GET /certificados/eco/datos/?empresa_id=X&mes=YYYY-MM
    """
    empresa_id = request.GET.get('empresa_id')
    mes_str    = request.GET.get('mes')  # 'YYYY-MM'

    if not empresa_id or not mes_str:
        return JsonResponse({'error': 'Parámetros incompletos'}, status=400)

    try:
        empresa = Empresa.objects.get(id=empresa_id)
        year, month = int(mes_str.split('-')[0]), int(mes_str.split('-')[1])
    except (Empresa.DoesNotExist, ValueError, IndexError):
        return JsonResponse({'error': 'Empresa o mes inválido'}, status=400)

    import calendar
    from django.db.models import Q
    from apps.empresas.models import SolicitudRecoleccion

    p_ini = f"{year}-{month:02d}-01"
    last_day = calendar.monthrange(year, month)[1]
    p_fin = f"{year}-{month:02d}-{last_day:02d}"

    # Acumulador por clave de material
    materiales_kg = {k: 0.0 for k, _ in MATERIALES_CERT}

    # 1. Servicios validados
    servicios = Servicio.objects.filter(
        empresa=empresa,
        modulo='reciclables',
        estado__in=['validado', 'documento_emitido', 'cerrado'],
    ).filter(
        Q(fecha_retiro_real__date__range=[p_ini, p_fin]) |
        Q(fecha_retiro_real__isnull=True, fecha_validacion__date__range=[p_ini, p_fin])
    )
    for s in servicios:
        reg = s.get_registro()
        if reg:
            mat_bd = getattr(reg, 'material', None) or ''
            eco_key = MATERIAL_KEYS.get(mat_bd.lower(), None)
            kg = float(getattr(reg, 'cantidad_kg', 0) or 0)
            if eco_key and kg and eco_key in materiales_kg:
                materiales_kg[eco_key] += kg

    # 2. Solicitudes de recolección
    solicitudes = SolicitudRecoleccion.objects.filter(
        empresa=empresa,
        modulo='reciclables',
        estado__in=['pendiente', 'asignada', 'completada'],
        fecha_solicitada__date__range=[p_ini, p_fin]
    )
    for sol in solicitudes:
        mat_bd = getattr(sol, 'tipo_material', '') or ''
        eco_key = MATERIAL_KEYS.get(mat_bd.lower(), None)
        kg = float(getattr(sol, 'cantidad_estimada', 0) or 0)
        if eco_key and kg and eco_key in materiales_kg:
            materiales_kg[eco_key] += kg

    # Calcular beneficios
    beneficios = calcular_eco_beneficios(materiales_kg)
    total_kg   = sum(materiales_kg.values())

    MESES_ES = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',
                7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}

    return JsonResponse({
        'empresa_nombre': empresa.nombre,
        'mes_nombre': MESES_ES.get(month, 'mes'),
        'anio': year,
        'materiales_kg': {k: round(v, 2) for k, v in materiales_kg.items()},
        'total_kg': round(total_kg, 2),
        'beneficios': beneficios,
    })


@method_decorator(login_required, name='dispatch')
class EcoEquivalenciaGeneradorView(View):
    template_name = 'certificados/eco_generador.html'

    def get(self, request):
        empresas = Empresa.objects.filter(estado='aprobada', activa=True)
        return render(request, self.template_name, {'empresas': empresas})

    def post(self, request):
        import calendar
        from django.core.files.base import ContentFile

        empresa_id = request.POST.get('empresa_id')
        mes_str    = request.POST.get('mes')  # 'YYYY-MM'
        empresas   = Empresa.objects.filter(estado='aprobada', activa=True)
        error      = None
        cert_url   = None
        cert_code  = None

        MESES_ES = {1:'enero',2:'febrero',3:'marzo',4:'abril',5:'mayo',6:'junio',
                    7:'julio',8:'agosto',9:'septiembre',10:'octubre',11:'noviembre',12:'diciembre'}

        if not empresa_id or not mes_str:
            error = 'Selecciona una empresa y un mes.'
        else:
            try:
                empresa = Empresa.objects.get(id=empresa_id)
                year, month = int(mes_str.split('-')[0]), int(mes_str.split('-')[1])

                # Leer kg desde POST (permite edición manual)
                materiales_kg = {}
                for mat_key, _ in MATERIALES_CERT:
                    val = request.POST.get(f'kg_{mat_key}', '0') or '0'
                    try:
                        materiales_kg[mat_key] = float(val)
                    except ValueError:
                        materiales_kg[mat_key] = 0.0

                total_kg = sum(materiales_kg.values())

                p_ini = f"{year}-{month:02d}-01"
                last_day = calendar.monthrange(year, month)[1]
                p_fin = f"{year}-{month:02d}-{last_day:02d}"

                # Crear registro de certificado en BD
                # Mapear a campos del modelo existente
                carton_kg  = materiales_kg.get('carton', 0) + materiales_kg.get('papel', 0)
                plastico_kg = materiales_kg.get('plastico', 0) + materiales_kg.get('film', 0)
                aluminio_kg = materiales_kg.get('aluminio', 0)
                vidrio_kg   = materiales_kg.get('vidrio', 0)
                otros_kg    = materiales_kg.get('pellon', 0) + materiales_kg.get('carretes', 0) + materiales_kg.get('sunchos', 0)
                total_rec   = carton_kg + plastico_kg + aluminio_kg + vidrio_kg + otros_kg

                # Desglose completo en JSON
                desglose = {
                    label: materiales_kg.get(key, 0)
                    for key, label in MATERIALES_CERT
                    if materiales_kg.get(key, 0) > 0
                }

                certificado = Certificado.objects.create(
                    empresa=empresa,
                    periodo_inicio=p_ini,
                    periodo_fin=p_fin,
                    total_reciclables_kg=total_rec,
                    total_rsd_kg=0,
                    total_escombros=0,
                    numero_servicios=0,
                    desglose_por_tipo=desglose,
                    generado_por=request.user
                )

                # Generar PDF
                datos_pdf = {
                    'empresa': empresa,
                    'mes_nombre': MESES_ES.get(month, 'mes'),
                    'anio': year,
                    'materiales_kg': materiales_kg,
                    'codigo': certificado.codigo_certificado,
                    'responsable_nombre': 'Leslie Plaza Vargas',
                    'responsable_cargo': 'DIRECTORA GENERAL',
                }
                pdf_bytes = generar_pdf_eco_equivalencia(datos_pdf, request=request)

                # Calcular hash
                pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()
                certificado.hash_sha256 = pdf_hash
                certificado.estado = 'vigente'

                filename = f"EcoEquiv_{certificado.codigo_certificado}.pdf"
                certificado.archivo_pdf.save(filename, ContentFile(pdf_bytes), save=False)
                certificado.save()

                cert_url  = request.build_absolute_uri(f"/certificados/descargar/{certificado.id}/")
                cert_code = certificado.codigo_certificado
                cert_id   = certificado.id

                AuditLog.registrar(
                    usuario=request.user,
                    accion='emision_doc',
                    modelo='Certificado',
                    registro_id=cert_code,
                    campo='archivo_pdf',
                    valor_anterior='',
                    valor_nuevo=f"SHA256:{pdf_hash[:16]}...",
                    detalles=f"Eco-Equivalencia {cert_code} emitido para {empresa.nombre} — {MESES_ES.get(month)} {year}.",
                    ip=request.META.get('REMOTE_ADDR')
                )

                messages.success(request, f"Certificado de Eco-Equivalencia {cert_code} generado exitosamente.")

                return render(request, self.template_name, {
                    'empresas': empresas,
                    'cert_id': cert_id,
                    'cert_code': cert_code,
                })

            except Empresa.DoesNotExist:
                error = 'Empresa no encontrada.'
            except Exception as e:
                error = f'Error al generar certificado: {e}'

        return render(request, self.template_name, {
            'empresas': empresas,
            'error': error,
        })
