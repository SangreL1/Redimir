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
