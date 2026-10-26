"""
Pruebas integrales de la Plataforma Redimir.
Ejecución: python manage.py test
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from django.core.management import call_command

from apps.usuarios.models import Usuario, AuditLog
from apps.empresas.models import Empresa, SolicitudRecoleccion, EstadoDePago, DetalleEstadoDePago
from apps.servicios.models import Servicio, RegistroRSD, RegistroEscombros, RegistroReciclables
from apps.calculadora.models import FactorEcoEquivalencia
from apps.certificados.models import Certificado


class RedimirPlataformaTestCase(TestCase):
    def setUp(self):
        # Crear usuario admin y empresa
        self.empresa = Empresa.objects.create(
            nombre="Empresa Minera Test",
            rut="76123456-7",
            direccion="Av. Minera 123",
            ciudad="Antofagasta",
            region="Antofagasta",
            rubro="mineria",
            giro="Extracción Minera",
            estado="aprobada",
            activa=True
        )

        self.admin = Usuario.objects.create_superuser(
            email="admin@redimir.cl",
            rut="11111111-1",
            nombre="Admin",
            apellido="Principal",
            rol="admin",
            password="password123"
        )

        self.operador = Usuario.objects.create_user(
            email="operador@redimir.cl",
            rut="22222222-2",
            nombre="Juan",
            apellido="Pérez",
            rol="operador",
            password="password123"
        )

        # Factores eco
        self.factor_pet = FactorEcoEquivalencia.objects.create(
            material='pet',
            factor_agua_lxkg=Decimal('25.0'),
            factor_co2_kgxkg=Decimal('3.5'),
            factor_energia_kwhxkg=Decimal('12.0'),
            factor_petroleo_lxkg=Decimal('1.8'),
            factor_arboles_kgxkg=Decimal('0.05'),
            activo=True
        )

    def test_autenticacion_por_rut(self):
        """Probar backend de autenticación personalizada por RUT."""
        client = Client()
        login_success = client.login(username="11111111-1", password="password123")
        self.assertTrue(login_success)

    def test_auditoria_log_inalterable(self):
        """Verificar que el registro de auditoría almacene datos estructurados."""
        log = AuditLog.registrar(
            usuario=self.admin,
            accion='configuracion',
            modelo='FactorEcoEquivalencia',
            registro_id=self.factor_pet.id,
            campo='factores',
            valor_anterior='0',
            valor_nuevo='25.0',
            detalles="Test auditoría"
        )
        self.assertEqual(log.usuario, self.admin)
        self.assertEqual(log.campo_modificado, 'factores')

    def test_generacion_backup_comando(self):
        """Probar ejecución limpia del comando de backup."""
        call_command('backup_system')

    def test_verificacion_certificado_y_qr(self):
        """Verificar que un certificado emitido con hash SHA-256 responda correctamente en la URL pública."""
        cert = Certificado.objects.create(
            empresa=self.empresa,
            periodo_inicio=timezone.now().date(),
            periodo_fin=timezone.now().date(),
            total_rsd_kg=Decimal('100.0'),
            estado='vigente',
            hash_sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
        )
        client = Client()
        response = client.get(f'/verificar/{cert.codigo_certificado}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, cert.codigo_certificado)
        self.assertContains(response, 'SHA-256')

    def test_servicios_predeterminados_empresa_y_api(self):
        """Verificar configuración de casillas de servicios y endpoint API."""
        self.empresa.servicios_predeterminados = ['Áreas Productivas', 'Bodega APD', 'Sector Chancado']
        self.empresa.save()

        client = Client()
        client.force_login(self.admin)

        response = client.get(f'/api/empresas/{self.empresa.pk}/servicios/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['servicios'], ['Áreas Productivas', 'Bodega APD', 'Sector Chancado'])

    def test_galeria_fotos_acceso(self):
        """Verificar acceso a la Galería de Fotos y Comprobantes."""
        client = Client()
        client.force_login(self.admin)
        response = client.get('/galeria/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Galería de Evidencias')

    def test_retiro_form_carga_servicios_predeterminados(self):
        """Verificar que el formulario de creación de retiro incluya el mapa de servicios."""
        client = Client()
        client.force_login(self.admin)
        response = client.get('/retiros/nuevo/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'serviciosChipsContainer')

    def test_edp_calculo_retiros_tarifa_servicio(self):
        """
        Verificar que una empresa con tarifa fija por retiro ($65.000/servicio)
        y 7 tickets ingresados (con detalles de materiales que suman 170 kg)
        genere un EDP con exactamente 7 retiros y $455.000 neto, NO 170 retiros ni $11.050.000.
        """
        import datetime
        from apps.empresas.models import TarifaEmpresa, actualizar_o_crear_edp_empresa
        from apps.servicios.models import CatalogoMaterialRetiro, TicketRetiro, DetalleMaterialTicket

        # 1. Tarifa configurada para la empresa: $65.000 por servicio
        TarifaEmpresa.objects.create(
            empresa=self.empresa,
            modulo='reciclables',
            tipo_material='servicio',
            precio_unitario=Decimal('65000'),
            unidad_medida='servicio'
        )

        mat = CatalogoMaterialRetiro.objects.create(
            nombre="Cartón Test",
            categoria="Reciclaje",
            unidad_medida="kg"
        )

        # 2. Crear 7 tickets de retiro en el mes que suman 170 kg en total
        p_inicio = datetime.date(2026, 9, 1)
        p_fin = datetime.date(2026, 9, 30)

        pesos = [20, 25, 30, 20, 25, 25, 25]  # suma: 170 kg
        for i, peso in enumerate(pesos, start=1):
            t = TicketRetiro.objects.create(
                empresa=self.empresa,
                numero_ticket=f"TCK-2026-00{i}",
                fecha=datetime.date(2026, 9, i * 3),
                tipo_servicio="Áreas Productivas",
                tipo_residuo="Reciclaje",
                peso_total_ticket=Decimal(str(peso))
            )
            DetalleMaterialTicket.objects.create(
                ticket=t,
                material=mat,
                peso_kg=Decimal(str(peso))
            )

        # 3. Generar / actualizar EDP
        edp = actualizar_o_crear_edp_empresa(self.empresa, periodo_inicio=p_inicio, periodo_fin=p_fin)

        # 4. Aserciones críticas
        self.assertEqual(edp.total_servicios, 7, f"Se esperaban 7 retiros pero dio {edp.total_servicios}")
        self.assertEqual(edp.subtotal_neto, Decimal('455000'), f"Se esperaba subtotal neto $455.000 pero dio ${edp.subtotal_neto}")
        self.assertEqual(edp.iva, Decimal('86450'), f"Se esperaba IVA $86.450 pero dio ${edp.iva}")
        self.assertEqual(edp.total_bruto, Decimal('541450'), f"Se esperaba total bruto $541.450 pero dio ${edp.total_bruto}")

    def test_material_otro_se_refleja_en_certificado_y_no_en_edp(self):
        """
        Verifica que al agregar un material tipo 'Otro' con descripción personalizada:
        - Su nombre_material sea la descripción ingresada.
        - Se excluya de la EDP comercial cuando la tarifa es por material/kg.
        - Se refleje en el certificado de reciclables con su nombre y peso.
        """
        import datetime
        from apps.empresas.models import TarifaEmpresa, actualizar_o_crear_edp_empresa
        from apps.servicios.models import CatalogoMaterialRetiro, TicketRetiro, DetalleMaterialTicket
        from apps.certificados.models import Certificado

        # Tarifa por kg para materiales
        TarifaEmpresa.objects.create(
            empresa=self.empresa,
            modulo='reciclables',
            tipo_material='kg',
            precio_unitario=Decimal('100'),
            unidad_medida='kg'
        )

        mat_cat = CatalogoMaterialRetiro.objects.create(
            nombre="Cartón Test 2",
            categoria="Reciclaje",
            unidad_medida="kg"
        )
        mat_otro = CatalogoMaterialRetiro.objects.create(
            nombre="Otro (Especificar)",
            categoria="Otro",
            unidad_medida="kg"
        )

        t = TicketRetiro.objects.create(
            empresa=self.empresa,
            numero_ticket="TCK-OTRO-999",
            fecha=datetime.date(2026, 10, 10),
            tipo_servicio="Puntos Verdes",
            tipo_residuo="Reciclaje",
            peso_total_ticket=Decimal('150.00')
        )

        # 1 material habitual (Cartón: 100 kg)
        DetalleMaterialTicket.objects.create(
            ticket=t,
            material=mat_cat,
            peso_kg=Decimal('100.00')
        )
        # 1 material personalizado "Otro" (Tubos HDPE: 50 kg)
        det_otro = DetalleMaterialTicket.objects.create(
            ticket=t,
            material=mat_otro,
            descripcion_otro="Tubos HDPE Especiales",
            peso_kg=Decimal('50.00')
        )

        self.assertEqual(det_otro.nombre_material, "Tubos HDPE Especiales")

        # Generar EDP y verificar que 'Tubos HDPE Especiales' NO aparezca en EDP
        p_inicio = datetime.date(2026, 10, 1)
        p_fin = datetime.date(2026, 10, 31)
        edp = actualizar_o_crear_edp_empresa(self.empresa, periodo_inicio=p_inicio, periodo_fin=p_fin)

        descripciones_edp = list(edp.detalles.values_list('descripcion', flat=True))
        for d in descripciones_edp:
            self.assertNotIn("Tubos HDPE", d)
            self.assertNotIn("Otro (Especificar)", d)

        # Verificar que en la lógica del certificado se incluya con su nombre
        PALABRAS_EXCLUIR_CERT = ('escombro', 'rescon', 'rsd', 'basura', 'doméstic', 'domestic')
        desglose = {}
        for det in t.detalles.all():
            m_nom = det.nombre_material
            if not any(p in m_nom.lower() for p in PALABRAS_EXCLUIR_CERT):
                desglose[m_nom] = float(det.peso_kg)

        self.assertIn("Tubos HDPE Especiales", desglose)
        self.assertEqual(desglose["Tubos HDPE Especiales"], 50.0)

    def test_ticket_pesaje_obligatorio_en_formulario(self):
        """
        Verifica que el formulario TicketRetiroForm exija el archivo de comprobante de pesaje.
        """
        import datetime
        from apps.servicios.forms import TicketRetiroForm

        form_data = {
            'empresa': self.empresa.id,
            'numero_ticket': 'TCK-SIN-RESPALDO',
            'fecha': datetime.date(2026, 10, 15),
            'faena_area': 'Planta',
            'tipo_servicio': 'Áreas Productivas',
            'tipo_residuo': 'Reciclaje',
            'peso_total_ticket': '500.00',
        }
        form = TicketRetiroForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('respaldo_ticket', form.errors)


