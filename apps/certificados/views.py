from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
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
                            rsd_kg += reg.cantidad_kg
                            desglose['RSD / Basura General'] = desglose.get('RSD / Basura General', 0) + reg.cantidad_kg
                        elif s.modulo == 'escombros' and reg:
                            escombros_total += 1
                            key = f"Escombros ({reg.get_unidad_display()})"
                            desglose[key] = desglose.get(key, 0) + float(reg.cantidad)
                        elif s.modulo == 'reciclables' and reg:
                            reciclables_kg += reg.cantidad_kg
                            key = f"Reciclables - {reg.get_material_display()}"
                            desglose[key] = desglose.get(key, 0) + reg.cantidad_kg

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

                    # Generar PDF con Branding Redimir
                    buffer = BytesIO()
                    # Doc properties
                    doc = SimpleDocTemplate(
                        buffer, 
                        pagesize=letter, 
                        rightMargin=60, 
                        leftMargin=60, 
                        topMargin=50, 
                        bottomMargin=50
                    )
                    
                    elements = []
                    styles = getSampleStyleSheet()
                    
                    # Colores Redimir
                    primary = colors.HexColor('#006BB8')
                    secondary = colors.HexColor('#95BF3C')
                    dark_gray = colors.HexColor('#2C3E50')
                    light_gray = colors.HexColor('#E1E4E7')
                    
                    # Estilos Personalizados
                    title_style = ParagraphStyle(
                        'RedimirTitle',
                        parent=styles['Heading1'],
                        fontSize=18,
                        textColor=primary,
                        alignment=1, # Center
                        spaceAfter=15,
                        fontName="Helvetica-Bold"
                    )
                    subtitle_style = ParagraphStyle(
                        'RedimirSubtitle',
                        parent=styles['Heading2'],
                        fontSize=14,
                        textColor=secondary,
                        alignment=1, # Center
                        spaceAfter=20,
                        fontName="Helvetica-Bold"
                    )
                    normal_bold = ParagraphStyle(
                        'NormalBold',
                        parent=styles['Normal'],
                        fontName="Helvetica-Bold",
                        fontSize=10,
                        textColor=dark_gray,
                        spaceAfter=6
                    )
                    
                    # Header
                    elements.append(Paragraph("SISTEMA DE GESTIÓN REDIMIR", title_style))
                    elements.append(Paragraph("CERTIFICADO OFICIAL DE TRAZABILIDAD DE RESIDUOS", subtitle_style))
                    elements.append(Spacer(1, 10))
                    
                    # Línea separadora
                    elements.append(HRFlowable(width="100%", thickness=2, color=primary, spaceAfter=20))
                    
                    # Datos Empresa
                    data_info = [
                        [Paragraph("<b>RAZÓN SOCIAL / EMPRESA:</b>", normal_bold), Paragraph(str(empresa.nombre), styles['Normal'])],
                        [Paragraph("<b>RUT:</b>", normal_bold), Paragraph(str(empresa.rut), styles['Normal'])],
                        [Paragraph("<b>PERÍODO CERTIFICADO:</b>", normal_bold), Paragraph(f"Desde {inicio} hasta {fin}", styles['Normal'])],
                        [Paragraph("<b>N° CERTIFICADO:</b>", normal_bold), Paragraph(f"{certificado.codigo_certificado}", styles['Normal'])],
                    ]
                    t_info = Table(data_info, colWidths=[200, 250])
                    t_info.setStyle(TableStyle([
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                    ]))
                    elements.append(t_info)
                    elements.append(Spacer(1, 20))
                    
                    elements.append(Paragraph("<b>RESUMEN DE RETIROS POR MÓDULO</b>", normal_bold))
                    elements.append(Spacer(1, 10))

                    # Tabla Desglose
                    data_tipos = [['Detalle del Material / Módulo', 'Cantidad']]
                    for k, v in desglose.items():
                        data_tipos.append([k, f"{v:g}"])
                    
                    t1 = Table(data_tipos, colWidths=[300, 150])
                    t1.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), primary),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 11),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                        ('TOPPADDING', (0, 0), (-1, 0), 10),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                        ('GRID', (0, 0), (-1, -1), 1, light_gray),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.whitesmoke])
                    ]))
                    elements.append(t1)
                    elements.append(Spacer(1, 25))

                    # Detalle de Servicios (Lotes)
                    elements.append(Paragraph("<b>DETALLE DE SERVICIOS PRESTADOS</b>", normal_bold))
                    elements.append(Spacer(1, 10))
                    
                    data_serv = [['Fecha', 'Módulo', 'Cantidad', 'Ticket Externo']]
                    for s in servicios:
                        reg = s.get_registro()
                        cant = "N/A"
                        tk = "N/A"
                        if reg:
                            tk = getattr(reg, 'ticket_externo', 'N/A')
                            if s.modulo == 'rsd':
                                cant = f"{reg.cantidad_kg} kg"
                            elif s.modulo == 'escombros':
                                cant = f"{reg.cantidad} {reg.get_unidad_display()}"
                            elif s.modulo == 'reciclables':
                                cant = f"{reg.cantidad_kg} kg"
                                
                        data_serv.append([
                            s.fecha_retiro_real.strftime("%d-%m-%Y") if s.fecha_retiro_real else "", 
                            s.get_modulo_display().upper(), 
                            cant, 
                            str(tk)
                        ])

                    t2 = Table(data_serv, colWidths=[80, 120, 100, 150])
                    t2.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), secondary),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('TOPPADDING', (0, 0), (-1, 0), 8),
                        ('GRID', (0, 0), (-1, -1), 1, light_gray),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAF9')])
                    ]))
                    elements.append(t2)
                    elements.append(Spacer(1, 20))

                    # ── QR CODE GENERATION (Punto 18) ──
                    import qrcode
                    qr_url = request.build_absolute_uri(f"/verificar/{certificado.codigo_certificado}/")
                    certificado.qr_certificado = qr_url
                    
                    qr_img = qrcode.make(qr_url)
                    qr_buffer = BytesIO()
                    qr_img.save(qr_buffer, 'PNG')
                    qr_buffer.seek(0)
                    
                    img_qr = Image(qr_buffer, width=1.1*inch, height=1.1*inch)
                    
                    # Tabla Footer con QR
                    footer_text = Paragraph(
                        f"<b>FOLIO OFICIAL:</b> {certificado.codigo_certificado}<br/>"
                        f"<b>ESTADO:</b> Verificado y Válido Legalmente<br/>"
                        f"Escanea este código QR con cualquier dispositivo móvil o accede a<br/>"
                        f"<u>{qr_url}</u> para comprobar la autenticidad en la plataforma Redimir.",
                        ParagraphStyle('QrFooterText', parent=styles['Normal'], fontSize=8, textColor=dark_gray, leading=11)
                    )
                    
                    t_qr = Table([[img_qr, footer_text]], colWidths=[100, 350])
                    t_qr.setStyle(TableStyle([
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('ALIGN', (0,0), (0,0), 'CENTER'),
                        ('ALIGN', (1,0), (1,0), 'LEFT'),
                    ]))
                    
                    elements.append(t_qr)
                    elements.append(Spacer(1, 10))
                    
                    elements.append(HRFlowable(width="100%", thickness=1, color=light_gray, spaceAfter=10))
                    elements.append(Paragraph(
                        "Este documento certifica que los residuos detallados fueron manejados y dispuestos "
                        "de acuerdo a la normativa legal vigente, en destinos e instalaciones autorizadas por Redimir.", 
                        ParagraphStyle('FooterText', parent=styles['Normal'], fontSize=7.5, textColor=colors.HexColor('#7F8C8D'), alignment=1)
                    ))
                    
                    # Save PDF
                    import hashlib
                    doc.build(elements)
                    pdf_content = buffer.getvalue()
                    buffer.close()

                    # Calcular Hash SHA-256 de integridad del PDF (Fase 5)
                    pdf_hash = hashlib.sha256(pdf_content).hexdigest()
                    certificado.hash_sha256 = pdf_hash
                    certificado.estado = 'vigente'

                    certificado.archivo_pdf.save(f"{certificado.codigo_certificado}.pdf", ContentFile(pdf_content))
                    certificado.save()
                    
                    # Auditoría de cambios estructurada (Fase 2 y 5)
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
                    messages.success(request, f"Certificado {certificado.codigo_certificado} generado exitosamente con QR verificable y firma digital SHA-256.")

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

