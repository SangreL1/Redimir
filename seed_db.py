import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.usuarios.models import Usuario
from apps.empresas.models import Empresa

def seed():
    print("Iniciando seed de base de datos...")
    
    # 1. Crear Empresas de prueba
    emp1, created1 = Empresa.objects.get_or_create(
        rut='77.777.777-7',
        defaults={
            'nombre': 'Retail Continental S.A.',
            'email_contacto': 'contacto@continental.cl',
            'telefono': '+56987654321',
            'direccion': 'Av. Vitacura 5000',
            'rubro': 'retail',
            'nombre_contacto': 'Pedro',
            'cargo_contacto': 'Gerente de Sustentabilidad',
            'estado': 'aprobada',
            'activa': True
        }
    )
    if created1:
        print("Empresa 'Retail Continental S.A.' creada.")
        
    emp2, created2 = Empresa.objects.get_or_create(
        rut='88.888.888-8',
        defaults={
            'nombre': 'Constructora Alfa',
            'email_contacto': 'obras@alfa.cl',
            'telefono': '+56999887766',
            'direccion': 'Santiago Centro 200',
            'rubro': 'construccion',
            'nombre_contacto': 'María',
            'cargo_contacto': 'Jefa de Patio',
            'estado': 'pendiente',
            'activa': True
        }
    )
    if created2:
        print("Empresa 'Constructora Alfa' (pendiente) creada.")

    # 2. Crear Superadministrador
    if not Usuario.objects.filter(rut='11.111.111-1').exists():
        admin = Usuario.objects.create_superuser(
            rut='11.111.111-1',
            password='admin123',
            nombre='Admin',
            apellido='Redimir',
            email='admin@redimir.cl'
        )
        print("Superusuario '11.111.111-1' creado (Clave: admin123).")
    
    # 3. Crear Operador Aprobado
    if not Usuario.objects.filter(rut='22.222.222-2').exists():
        operador = Usuario.objects.create_user(
            rut='22.222.222-2',
            password='operador123',
            nombre='Juan',
            apellido='Operador',
            email='juan@redimir.cl',
            telefono='+56955554444',
            rol='operador',
            estado='aprobado',
            empresa=emp1
        )
        print("Operador Aprobado '22.222.222-2' creado (Clave: operador123).")

    # 4. Crear Operador Pendiente
    if not Usuario.objects.filter(rut='33.333.333-3').exists():
        operador_pend = Usuario.objects.create_user(
            rut='33.333.333-3',
            password='operador123',
            nombre='Lucas',
            apellido='Pendiente',
            email='lucas@redimir.cl',
            telefono='+56955553333',
            rol='operador',
            estado='pendiente',
            empresa=emp1
        )
        print("Operador Pendiente '33.333.333-3' creado.")

    print("Seed finalizado con éxito.")

if __name__ == '__main__':
    seed()
