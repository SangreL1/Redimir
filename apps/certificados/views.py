from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.views import View
from django.shortcuts import render
from django.core.files.base import ContentFile
from io import BytesIO
from .models import Certificado
from apps.servicios.models import Servicio
from apps.empresas.models import Empresa
from django.db.models import Sum

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

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
                # Obtenemos servicios validados en el rango de fechas
                servicios = Servicio.objects.filter(
                    empresa=empresa, 
                    estado='validado',
                    fecha_retiro_real__date__range=[inicio, fin]
                )

                if not servicios.exists():
                    error = 'No hay servicios validados para esta empresa en el período indicado.'
                else:
                    # Calcular totales
                    rsd_kg = 0
                    escombros_total = 0
                    reciclables_kg = 0
                    
                    desglose = {}
                    
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

                    # Crear Certificado
                    certificado = Certificado.objects.create(
                        empresa=empresa,
                        periodo_inicio=inicio,
                        periodo_fin=fin,
                        total_rsd_kg=rsd_kg,
                        total_escombros=escombros_total,
                        total_reciclables_kg=reciclables_kg,
                        numero_servicios=servicios.count(),
                        desglose_por_tipo=desglose,
                        generado_por=request.user
                    )
                    certificado.servicios.set(servicios)

                    # ── Generar PDF con Layout Identico al Certificado Canva Redimir ──
                    from django.conf import settings
                    import os, hashlib, qrcode
                    from reportlab.lib.pagesizes import A4
                    from reportlab.lib.units import cm
                    from reportlab.platypus import KeepTogether

                    MESES_ES = {
                        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
                        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                    }

                    DIAS_ES = {
                        0: 'LUNES', 1: 'MARTES', 2: 'MIÉRCOLES', 3: 'JUEVES',
                        4: 'VIERNES', 5: 'SÁBADO', 6: 'DOMINGO'
                    }

                    buffer = BytesIO()
                    doc = SimpleDocTemplate(
                        buffer, 
                        pagesize=A4, 
                        rightMargin=50, 
                        leftMargin=50, 
                        topMargin=40, 
                        bottomMargin=40
                    )
                    
                    elements = []
                    styles = getSampleStyleSheet()
                    
                    primary_green = colors.HexColor('#95BF3C')
                    text_dark = colors.HexColor('#000000')
                    text_gray = colors.HexColor('#737373')
                    
                    title_style = ParagraphStyle(
                        'CertTitle',
                        fontName='Helvetica-Bold',
                        fontSize=22,
                        leading=26,
                        textColor=text_dark,
                        alignment=1,
                        spaceAfter=14
                    )
                    
                    body_gray = ParagraphStyle(
                        'CertBodyGray',
                        fontName='Helvetica',
                        fontSize=10,
                        leading=14,
                        textColor=text_gray,
                        alignment=0
                    )
                    
                    label_style = ParagraphStyle(
                        'CertLabel',
                        fontName='Helvetica-Bold',
                        fontSize=10.5,
                        leading=14,
                        textColor=text_dark
                    )
                    
                    val_style = ParagraphStyle(
                        'CertVal',
                        fontName='Helvetica',
                        fontSize=10.5,
                        leading=14,
                        textColor=text_dark
                    )
                    
                    date_style = ParagraphStyle(
                        'CertDate',
                        fontName='Helvetica',
                        fontSize=11,
                        leading=13,
                        textColor=text_dark,
                        alignment=2
                    )

                    # 1. Header (Logo Left + Contacts Right)
                    logo_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'redimir_logo_cert.png')
                    logo_img = Image(logo_path, width=5.0*cm, height=5.0*cm * (91/558)) if os.path.exists(logo_path) else Paragraph("<b>REDIMIR</b>", title_style)

                    contact_html = '''
                    <font size=8 color='#000000'>
                    <b>(56) 9 4252 5059</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Pasaje Trans DyF 1643, Calama<br/>
                    <b>redimir.cl</b> &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; contacto@redimir.cl
                    </font>
                    '''
                    contact_p = Paragraph(contact_html, ParagraphStyle('HeaderContact', fontName='Helvetica', fontSize=8, leading=12, alignment=2))

                    t_header = Table([[logo_img, contact_p]], colWidths=[180, 315])
                    t_header.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('ALIGN', (0,0), (0,0), 'LEFT'),
                        ('ALIGN', (1,0), (1,0), 'RIGHT'),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                    ]))
                    elements.append(t_header)
                    elements.append(Spacer(1, 4))

                    # 2. Línea divisoria negra superior
                    elements.append(HRFlowable(width='100%', thickness=1, color=text_dark, spaceBefore=4, spaceAfter=20))

                    # 3. Fecha de Emisión en español
                    from datetime import datetime
                    fecha_obj = timezone.now()
                    dia_semana = DIAS_ES[fecha_obj.weekday()]
                    mes_nombre = MESES_ES[fecha_obj.month].upper()
                    fecha_str = f"{dia_semana}, {fecha_obj.day:02d} DE {mes_nombre} {fecha_obj.year}"
                    elements.append(Paragraph(fecha_str, date_style))
                    elements.append(Spacer(1, 20))

                    # 4. Título Principal
                    elements.append(Paragraph("Certificado de Transporte y<br/>Trazabilidad de Residuos", title_style))
                    elements.append(Spacer(1, 25))

                    # 5. Declaración Legal N° 1618 SEREMI DE SALUD
                    p1_text = (
                        "Empresa de gestión de residuos <b>Redimir SpA</b> con RUT No. <b>76.781.064-4</b>, certifica que "
                        "realizó el traslado a disposición final de residuos, en norma y bajo la resolución de "
                        "transporte de residuos no peligrosos <b>N° 1618</b> de la <b>SEREMI DE SALUD DE ANTOFAGASTA</b>."
                    )
                    elements.append(Paragraph(p1_text, body_gray))
                    elements.append(Spacer(1, 15))

                    # Mes del período certificado
                    from datetime import datetime as dt
                    try:
                        dt_start = dt.strptime(inicio, "%Y-%m-%d")
                        mes_periodo = MESES_ES[dt_start.month]
                        anio_periodo = dt_start.year
                    except Exception:
                        mes_periodo = MESES_ES[fecha_obj.month]
                        anio_periodo = fecha_obj.year

                    p2_text = f"En el mes de <b>{mes_periodo}</b> del <b>{anio_periodo}</b> se han trasladado los residuos no peligrosos desde:"
                    elements.append(Paragraph(p2_text, body_gray))
                    elements.append(Spacer(1, 25))

                    # 6. Formatear Desglose para la Tabla (Formato limpio sin cajas grises)
                    tipos_lines = []
                    for k, v in desglose.items():
                        if isinstance(v, (int, float)):
                            tipos_lines.append(f"{k}: {v:g} Kg." if "m3" not in k.lower() else f"{k}: {v:g}")
                        else:
                            tipos_lines.append(f"{k}: {v}")
                    
                    tipos_text = "<br/>".join(tipos_lines) if tipos_lines else "Residuos Varios"

                    total_kg_acum = float(rsd_kg) + float(reciclables_kg)
                    cant_total_str = f"{total_kg_acum:g} Kg." if total_kg_acum > 0 else f"{escombros_total} Retiro(s)"

                    destinos_set = set()
                    for s in servicios:
                        reg = s.get_registro()
                        if reg:
                            d = getattr(reg, 'destino_receptor', None) or getattr(reg, 'destino', None) or getattr(reg, 'destino_otro', None)
                            if d:
                                destinos_set.add(str(d).title())
                    destino_final_str = ", ".join(destinos_set) if destinos_set else "Reciclados Industriales."

                    grid_data = [
                        [Paragraph("Institución:", label_style), Paragraph(str(empresa.nombre), val_style)],
                        [Paragraph("Dirección:", label_style), Paragraph(str(empresa.direccion or "Calama, Región de Antofagasta"), val_style)],
                        [Paragraph("Tipos de Residuos:", label_style), Paragraph(tipos_text, val_style)],
                        [Paragraph("Cantidad:", label_style), Paragraph(cant_total_str, val_style)],
                        [Paragraph("Destino:", label_style), Paragraph(destino_final_str, val_style)],
                    ]

                    t_grid = Table(grid_data, colWidths=[150, 345])
                    t_grid.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'TOP'),
                        ('TOPPADDING', (0,0), (-1,-1), 4),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                        ('LEFTPADDING', (0,0), (-1,-1), 0),
                        ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ]))
                    elements.append(t_grid)
                    elements.append(Spacer(1, 30))

                    # 7. Sub-declaración de Trazabilidad
                    p3_text = "Los residuos antes nombrados cumplieron con la trazabilidad sustentable, siendo derivados a las plantas de reciclaje antes mencionadas."
                    elements.append(Paragraph(p3_text, body_gray))
                    elements.append(Spacer(1, 30))

                    # 8. Ubicación
                    elements.append(Paragraph("Calama, Región de Antofagasta, Chile.", body_gray))
                    elements.append(Spacer(1, 40))

                    # 9. Bloque de Firmas, QR y Sello
                    firma_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'firma_directora.png')
                    firma_img = Image(firma_path, width=4.5*cm, height=4.5*cm * (313/917)) if os.path.exists(firma_path) else Spacer(1, 20)

                    sig_text_html = '''
                    <font size=12 color='#000000'><b>Leslie Plaza Vargas</b></font><br/>
                    <font size=9.5 color='#737373'>DIRECTORA GENERAL</font><br/>
                    <font size=9.5 color='#737373'>REDIMIR SpA — Gestión de Residuos</font>
                    '''
                    sig_p = Paragraph(sig_text_html, ParagraphStyle('SigP', fontName='Helvetica', fontSize=9.5, leading=13))

                    left_sig_block = [
                        firma_img,
                        Spacer(1, -10),
                        sig_p
                    ]

                    # QR Code
                    qr_url = request.build_absolute_uri(f"/verificar/{certificado.codigo_certificado}/")
                    certificado.qr_certificado = qr_url

                    qr_img_obj = qrcode.make(qr_url)
                    qr_buffer = BytesIO()
                    qr_img_obj.save(qr_buffer, 'PNG')
                    qr_buffer.seek(0)

                    img_qr = Image(qr_buffer, width=1.8*cm, height=1.8*cm)
                    
                    icon_bottom_path = os.path.join(settings.BASE_DIR, 'static', 'img', 'cert_icon_bottom.png')
                    icon_img = Image(icon_bottom_path, width=1.6*cm, height=1.6*cm * (334/359)) if os.path.exists(icon_bottom_path) else Spacer(1, 10)

                    qr_info_html = f'''
                    <font size=7.5 color='#737373'>
                    <b>FOLIO:</b> {certificado.codigo_certificado}<br/>
                    <b>VERIFICADO ONLINE</b><br/>
                    Escanea para autenticidad.
                    </font>
                    '''
                    qr_p = Paragraph(qr_info_html, ParagraphStyle('QrP', fontName='Helvetica', fontSize=7.5, leading=9.5, alignment=1))

                    right_qr_table = Table([[icon_img, img_qr], [None, qr_p]], colWidths=[55, 80])
                    right_qr_table.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('SPAN', (1,1), (1,1)),
                    ]))

                    t_footer_main = Table([[left_sig_block, right_qr_table]], colWidths=[340, 155])
                    t_footer_main.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
                        ('ALIGN', (1,0), (1,0), 'RIGHT'),
                    ]))

                    elements.append(KeepTogether(t_footer_main))

                    def draw_canvas_decorations(canvas, doc):
                        canvas.saveState()
                        canvas.setFillColor(primary_green)
                        canvas.rect(0, 0, 595.27, 20, fill=1, stroke=0)
                        canvas.restoreState()

                    doc.build(elements, onFirstPage=draw_canvas_decorations, onLaterPages=draw_canvas_decorations)
                    pdf_content = buffer.getvalue()
                    buffer.close()

                    # Calcular Hash SHA-256 de integridad del PDF
                    pdf_hash = hashlib.sha256(pdf_content).hexdigest()
                    certificado.hash_sha256 = pdf_hash
                    certificado.estado = 'vigente'

                    certificado.archivo_pdf.save(f"{certificado.codigo_certificado}.pdf", ContentFile(pdf_content))
                    certificado.save()
                    
                    # Auditoría de cambios estructurada
                    from apps.usuarios.models import AuditLog
                    AuditLog.registrar(
                        usuario=request.user,
                        accion='emision_doc',
                        modelo='Certificado',
                        registro_id=certificado.codigo_certificado,
                        campo='archivo_pdf',
                        valor_anterior='',
                        valor_nuevo=f"SHA256:{pdf_hash[:16]}...",
                        detalles=f"Certificado emitido para {empresa.nombre} del {inicio} al {fin}. Hash SHA-256: {pdf_hash}",
                        ip=request.META.get('REMOTE_ADDR')
                    )

                    # Preparar mensaje de éxito
                    from django.contrib import messages
                    messages.success(request, f"Certificado {certificado.codigo_certificado} generado exitosamente con el formato oficial Redimir (QR y firma SHA-256).")

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
    Punto 18 del Checklist Maestro Redimir.
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

