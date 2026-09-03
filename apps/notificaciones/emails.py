"""
SERVICIO CENTRALIZADO DE ENVÍO DE CORREOS — REDIMIR SpA
Maneja plantillas HTML institucionales y adjuntos en PDF para:
1. Certificados oficiales y de Eco-Equivalencia (con PDF adjunto)
2. Estados de Pago (EDP) comerciales
3. Notificaciones de retiros de residuos completados y validados
"""
import os
import logging
from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

logger = logging.getLogger('redimir')


def _plantilla_base_html(titulo_banner, contenido_cuerpo):
    """Genera la estructura HTML institucional de Redimir con diseño responsive y corporativo."""
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo_banner}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F8FAFC; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #1E293B;">
<table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed; background-color: #F8FAFC; padding: 30px 10px;">
    <tr>
        <td align="center">
            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 620px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.06); border: 1px solid #E2E8F0;">
                <!-- Header Banner -->
                <tr>
                    <td style="background: linear-gradient(135deg, #004A80 0%, #006BB8 100%); padding: 24px 30px; text-align: left;">
                        <table border="0" cellpadding="0" cellspacing="0" width="100%">
                            <tr>
                                <td>
                                    <h1 style="color: #FFFFFF; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: 1px;">
                                        REDIMIR<span style="color: #95BF3C;">+</span>
                                    </h1>
                                    <p style="color: #BAE6FD; margin: 4px 0 0 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px;">
                                        Gestión de Residuos, Asesoría & Logística SpA
                                    </p>
                                </td>
                                <td align="right">
                                    <span style="background-color: rgba(255,255,255,0.15); color: #FFFFFF; padding: 6px 12px; border-radius: 20px; font-size: 11px; font-weight: 600;">
                                        Documento Oficial
                                    </span>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>

                <!-- Línea de acento verde -->
                <tr>
                    <td height="4" style="background-color: #95BF3C; line-height: 4px; font-size: 4px;">&nbsp;</td>
                </tr>

                <!-- Contenido Principal -->
                <tr>
                    <td style="padding: 30px;">
                        {contenido_cuerpo}
                    </td>
                </tr>

                <!-- Footer Institucional -->
                <tr>
                    <td style="background-color: #0F172A; padding: 20px 30px; text-align: center; color: #94A3B8; font-size: 12px; line-height: 18px;">
                        <p style="margin: 0 0 6px 0; color: #E2E8F0; font-weight: 600;">REDIMIR SpA — Calama, Región de Antofagasta</p>
                        <p style="margin: 0 0 6px 0;">Pasaje Trans DyF 1643 &bull; Tel: (56) 9 4252 5059</p>
                        <p style="margin: 0 0 10px 0;">contacto@redimir.cl &bull; <a href="https://redimir.cl" style="color: #95BF3C; text-decoration: none;">www.redimir.cl</a></p>
                        <p style="margin: 0; font-size: 10px; color: #64748B;">Este es un correo automático emitido por la Plataforma de Trazabilidad y Gestión Ambiental de Redimir SpA.</p>
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
</body>
</html>"""


# ==============================================================================
# 1. ENVÍO DE CERTIFICADO (PDF ADJUNTO)
# ==============================================================================

def enviar_email_certificado(certificado, destinatario=None, request=None):
    """
    Envía por correo el Certificado oficial con el archivo PDF adjunto.
    Retorna: (exito: bool, mensaje: str)
    """
    empresa = certificado.empresa
    email_to = destinatario or getattr(empresa, 'email_contacto', None)

    if not email_to:
        return False, f"La empresa {empresa.nombre} no tiene un correo de contacto registrado."

    # Asegurar que el PDF esté generado
    from apps.certificados.views import generar_pdf_certificado
    if not certificado.archivo_pdf or not os.path.exists(certificado.archivo_pdf.path):
        try:
            generar_pdf_certificado(certificado, request=request)
            certificado.refresh_from_db()
        except Exception as e:
            logger.error(f"Error generando PDF para certificado {certificado.codigo_certificado}: {e}")
            return False, f"Error al generar el PDF del certificado: {e}"

    if not certificado.archivo_pdf or not os.path.exists(certificado.archivo_pdf.path):
        return False, "No se encontró el archivo PDF del certificado para adjuntar."

    asunto = f"📜 Certificado Oficial de Gestión y Disposición {certificado.codigo_certificado} — Redimir SpA"

    ini_str = certificado.periodo_inicio.strftime('%d/%m/%Y')
    fin_str = certificado.periodo_fin.strftime('%d/%m/%Y')
    total_kg = (certificado.total_reciclables_kg or 0) + (certificado.total_rsd_kg or 0)

    cuerpo = f"""
    <h2 style="color: #004A80; font-size: 18px; margin: 0 0 12px 0;">Estimados señores de {empresa.nombre},</h2>
    <p style="font-size: 14px; line-height: 22px; margin-bottom: 20px;">
        Nos es grato adjuntar su <strong>Certificado Oficial de Disposición y Trazabilidad Ambiental</strong> correspondiente al período del <strong>{ini_str} al {fin_str}</strong>.
    </p>

    <!-- Caja resumen -->
    <table border="0" cellpadding="12" cellspacing="0" width="100%" style="background-color: #F1F5F9; border-radius: 8px; margin-bottom: 24px; border-left: 4px solid #006BB8;">
        <tr>
            <td style="font-size: 13px; line-height: 20px;">
                <strong>N° Certificado:</strong> <span style="color: #006BB8; font-weight: 700;">{certificado.codigo_certificado}</span><br>
                <strong>Empresa / Razón Social:</strong> {empresa.nombre} ({empresa.rut})<br>
                <strong>Período Certificado:</strong> {ini_str} al {fin_str}<br>
                <strong>Total Residuos Gestionados:</strong> {total_kg:,.1f} kg.<br>
                <strong>Fecha de Emisión:</strong> {certificado.fecha_generacion.strftime('%d/%m/%Y %H:%M')}<br>
                <strong>Hash de Autenticidad (SHA-256):</strong> <span style="font-family: monospace; font-size: 11px; color: #475569;">{certificado.hash_sha256[:20]}...</span>
            </td>
        </tr>
    </table>

    <p style="font-size: 14px; line-height: 22px; margin-bottom: 16px;">
        El documento oficial en formato PDF se encuentra adjunto a este mensaje y cuenta con su respectivo código QR para validación pública e inmediata ante auditorías y entidades fiscalizadoras.
    </p>

    <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 12px; margin-bottom: 20px;">
        <p style="margin: 0; font-size: 13px; color: #065F46;">
            🌱 <em>Gracias por su compromiso con la gestión responsable de residuos y la sustentabilidad ambiental.</em>
        </p>
    </div>
    """

    html_content = _plantilla_base_html("Certificado Oficial Redimir", cuerpo)

    try:
        email = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[email_to],
        )
        email.content_subtype = "html"

        # Adjuntar PDF
        with open(certificado.archivo_pdf.path, 'rb') as f:
            email.attach(
                f"Certificado_{certificado.codigo_certificado}.pdf",
                f.read(),
                'application/pdf'
            )

        email.send(fail_silently=False)
        logger.info(f"Certificado {certificado.codigo_certificado} enviado por correo a {email_to}")
        return True, email_to
    except Exception as e:
        logger.error(f"Error enviando correo de certificado {certificado.codigo_certificado} a {email_to}: {e}")
        return False, str(e)


# ==============================================================================
# 2. ENVÍO DE ESTADO DE PAGO (EDP)
# ==============================================================================

def enviar_email_edp(edp, destinatario=None):
    """
    Envía por correo el Estado de Pago (EDP) comercial al cliente con su desglose.
    Retorna: (exito: bool, mensaje: str)
    """
    empresa = edp.empresa
    email_to = destinatario or getattr(empresa, 'email_contacto', None)

    if not email_to:
        return False, f"La empresa {empresa.nombre} no tiene un correo de contacto registrado."

    asunto = f"💼 Estado de Pago Comercial {edp.numero_edp} — Redimir SpA"

    ini_str = edp.periodo_inicio.strftime('%d/%m/%Y')
    fin_str = edp.periodo_fin.strftime('%d/%m/%Y')

    # Desglose de servicios / detalles del EDP
    detalles_html = ""
    detalles = edp.detalles.all()
    for d in detalles:
        f_txt = d.fechas_texto or (d.fecha_servicio.strftime('%d/%m/%Y') if d.fecha_servicio else "")
        detalles_html += f"""
        <tr>
            <td style="padding: 8px 10px; border-bottom: 1px solid #E2E8F0; font-size: 12px;">
                <strong>{d.descripcion}</strong>
                {f'<br><small style="color:#64748B;">{f_txt}</small>' if f_txt else ''}
            </td>
            <td style="padding: 8px 10px; border-bottom: 1px solid #E2E8F0; font-size: 12px; text-align: center;">{float(d.cantidad or 0):g}</td>
            <td style="padding: 8px 10px; border-bottom: 1px solid #E2E8F0; font-size: 12px; text-align: right;">${int(d.tarifa_unitaria or 0):,}</td>
            <td style="padding: 8px 10px; border-bottom: 1px solid #E2E8F0; font-size: 12px; text-align: right; font-weight: 700; color: #004A80;">${int(d.subtotal or 0):,}</td>
        </tr>
        """

    cuerpo = f"""
    <h2 style="color: #004A80; font-size: 18px; margin: 0 0 12px 0;">Estimados señores de {empresa.nombre},</h2>
    <p style="font-size: 14px; line-height: 22px; margin-bottom: 20px;">
        Adjuntamos el resumen del <strong>Estado de Pago (EDP) N° {edp.numero_edp}</strong> por los servicios logísticos y de gestión ambiental prestados durante el período del <strong>{ini_str} al {fin_str}</strong>.
    </p>

    <!-- Tarjeta de totales -->
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; margin-bottom: 20px;">
        <tr>
            <td style="padding: 16px 20px;">
                <table border="0" cellpadding="4" cellspacing="0" width="100%">
                    <tr>
                        <td style="font-size: 13px; color: #64748B;">N° de Retiros Realizados:</td>
                        <td style="font-size: 13px; font-weight: 700; text-align: right;">{edp.total_servicios} retiros</td>
                    </tr>
                    <tr>
                        <td style="font-size: 13px; color: #64748B;">Subtotal Neto:</td>
                        <td style="font-size: 13px; font-weight: 700; text-align: right;">${int(edp.subtotal_neto or 0):,}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 13px; color: #64748B;">IVA (19%):</td>
                        <td style="font-size: 13px; font-weight: 700; text-align: right;">${int(edp.iva or 0):,}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="border-top: 2px solid #CBD5E1; padding-top: 8px;"></td>
                    </tr>
                    <tr>
                        <td style="font-size: 16px; font-weight: 800; color: #004A80;">TOTAL A PAGAR:</td>
                        <td style="font-size: 18px; font-weight: 800; color: #006BB8; text-align: right;">${int(edp.total_bruto or 0):,} CLP</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <!-- Tabla desglose si hay servicios / detalles -->
    <h3 style="font-size: 14px; color: #1E293B; margin: 16px 0 8px 0; text-transform: uppercase;">Detalle de Servicios Incluidos</h3>
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-collapse: collapse; margin-bottom: 24px;">
        <thead>
            <tr style="background-color: #000000; color: #FFFFFF; text-align: left;">
                <th style="padding: 8px 10px; font-size: 11px; color: #FFFFFF;">Descripción</th>
                <th style="padding: 8px 10px; font-size: 11px; color: #FFFFFF; text-align: center;">Cantidad</th>
                <th style="padding: 8px 10px; font-size: 11px; color: #FFFFFF; text-align: right;">Tarifa</th>
                <th style="padding: 8px 10px; font-size: 11px; color: #FFFFFF; text-align: right;">Subtotal</th>
            </tr>
        </thead>
        <tbody>
            {detalles_html if detalles_html else '<tr><td colspan="4" style="text-align:center; padding:12px; font-size:12px; color:#64748B;">No hay ítems registrados.</td></tr>'}
        </tbody>
    </table>

    <!-- Datos para transferencia -->
    <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
        <h4 style="margin: 0 0 8px 0; color: #166534; font-size: 13px; text-transform: uppercase;">Datos de Transferencia Bancaria</h4>
        <p style="margin: 0; font-size: 12px; line-height: 18px; color: #15803D;">
            <strong>Razón Social:</strong> REDIMIR SpA<br>
            <strong>RUT:</strong> 77.854.321-K<br>
            <strong>Banco:</strong> Banco de Chile / Banco Estado<br>
            <strong>Tipo de Cuenta:</strong> Cuenta Corriente<br>
            <strong>Correo comprobantes:</strong> contacto@redimir.cl
        </p>
    </div>
    """

    html_content = _plantilla_base_html("Estado de Pago Redimir", cuerpo)

    try:
        email = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[email_to],
        )
        email.content_subtype = "html"

        # Generar y adjuntar documento oficial PDF del EDP
        try:
            from apps.empresas.pdf import generar_pdf_edp
            pdf_bytes = generar_pdf_edp(edp)
            email.attach(
                f"Estado_de_Pago_{edp.numero_edp}.pdf",
                pdf_bytes,
                'application/pdf'
            )
        except Exception as e:
            logger.error(f"Error adjuntando PDF a EDP {edp.numero_edp}: {e}")

        email.send(fail_silently=False)
        logger.info(f"EDP {edp.numero_edp} enviado por correo a {email_to}")
        return True, email_to
    except Exception as e:
        logger.error(f"Error enviando correo de EDP {edp.numero_edp} a {email_to}: {e}")
        return False, str(e)


# ==============================================================================
# 3. ENVÍO DE NOTIFICACIÓN DE RETIRO DE RESIDUOS (COMPLETADO / VALIDADO)
# ==============================================================================

def enviar_email_retiro_validado(servicio, destinatario=None):
    """
    Envía comprobante por correo a la empresa cuando un retiro ha sido ejecutado y validado.
    Retorna: (exito: bool, mensaje: str)
    """
    empresa = servicio.empresa
    email_to = destinatario or getattr(empresa, 'email_contacto', None)

    if not email_to:
        return False, f"La empresa {empresa.nombre} no tiene un correo de contacto registrado."

    asunto = f"✅ Comprobante de Retiro Validado: Folio #{servicio.pk} ({servicio.get_modulo_display()}) — Redimir SpA"

    fecha_txt = (servicio.fecha_retiro_real or servicio.fecha_programada or timezone.now()).strftime('%d/%m/%Y %H:%M')
    operador_nombre = getattr(servicio.operador, 'nombre_completo', None) if servicio.operador else "Equipo Operativo Redimir"
    destino_txt = servicio.planta_destino or "Planta de Valorización / Disposición Autorizada"

    reg = servicio.get_registro()
    cantidad_txt = ""
    ticket_txt = ""
    if reg:
        if hasattr(reg, 'cantidad_kg') and reg.cantidad_kg:
            cantidad_txt = f"{float(reg.cantidad_kg):g} kg."
        elif hasattr(reg, 'cantidad_valor') and reg.cantidad_valor:
            unidad = getattr(reg, 'unidad_medida', 'kg')
            cantidad_txt = f"{float(reg.cantidad_valor):g} {unidad}"
        
        ticket_txt = getattr(reg, 'ticket_externo', None) or getattr(reg, 'ticket_pesaje', None) or ""

    if not cantidad_txt:
        cantidad_txt = f"{float(servicio.cantidad_estimada or 0):g} {servicio.unidad_estimada}" if servicio.cantidad_estimada else "Conforme"

    cuerpo = f"""
    <h2 style="color: #004A80; font-size: 18px; margin: 0 0 12px 0;">Estimados señores de {empresa.nombre},</h2>
    <p style="font-size: 14px; line-height: 22px; margin-bottom: 20px;">
        Les informamos que el retiro de residuos <strong>Folio #{servicio.pk}</strong> ha sido ejecutado y validado conforme en nuestra plataforma.
    </p>

    <!-- Ficha Técnica del Retiro -->
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; margin-bottom: 20px;">
        <tr>
            <td style="padding: 16px 20px;">
                <table border="0" cellpadding="5" cellspacing="0" width="100%">
                    <tr>
                        <td width="35%" style="font-size: 12px; color: #64748B; font-weight: 600;">MÓDULO:</td>
                        <td style="font-size: 13px; font-weight: 700; color: #006BB8;">{servicio.get_modulo_display()}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #64748B; font-weight: 600;">FECHA Y HORA:</td>
                        <td style="font-size: 13px; color: #1E293B;">{fecha_txt}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #64748B; font-weight: 600;">DIRECCIÓN DE RETIRO:</td>
                        <td style="font-size: 13px; color: #1E293B;">{servicio.direccion}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #64748B; font-weight: 600;">CANTIDAD VALIDADA:</td>
                        <td style="font-size: 15px; font-weight: 800; color: #16A34A;">{cantidad_txt}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #64748B; font-weight: 600;">OPERADOR A CARGO:</td>
                        <td style="font-size: 13px; color: #1E293B;">{operador_nombre}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #64748B; font-weight: 600;">DESTINO / PLANTA:</td>
                        <td style="font-size: 13px; color: #1E293B;">{destino_txt} {f'&bull; Ticket: <strong>{ticket_txt}</strong>' if ticket_txt else ''}</td>
                    </tr>
                    <tr>
                        <td style="font-size: 12px; color: #64748B; font-weight: 600;">ESTADO TRAZABILIDAD:</td>
                        <td style="font-size: 12px; color: #1E293B;"><span style="background-color: #DCFCE7; color: #15803D; padding: 2px 8px; border-radius: 12px; font-weight: 700;">Validado Conforme</span></td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <div style="background-color: #F1F5F9; border-radius: 8px; padding: 14px; margin-bottom: 20px;">
        <p style="margin: 0; font-size: 13px; color: #475569; line-height: 20px;">
            ℹ️ Este registro ya forma parte de su historial de trazabilidad ambiental mensual y será consolidado en su próximo <strong>Certificado Oficial y Estado de Pago</strong>.
        </p>
    </div>
    """

    html_content = _plantilla_base_html("Comprobante de Retiro Validado", cuerpo)

    try:
        email = EmailMessage(
            subject=asunto,
            body=html_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            to=[email_to],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
        logger.info(f"Comprobante de retiro #{servicio.pk} enviado por correo a {email_to}")
        return True, email_to
    except Exception as e:
        logger.error(f"Error enviando comprobante de retiro #{servicio.pk} a {email_to}: {e}")
        return False, str(e)
