import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.usuarios.models import Usuario
from apps.empresas.models import Empresa

def run_seed():
    # Creamos una Empresa de prueba
    empresa, created = Empresa.objects.get_or_create(
        rut='77.123.456-1',
        defaults={
            'nombre': 'Industrias de Reciclaje SA',
            'email_contacto': 'contacto@industrias.cl',
            'activa': True
        }
    )

    # Creamos un Administrador del Sistema
    if not Usuario.objects.filter(email='admin@redimir.cl').exists():
        Usuario.objects.create_superuser(
            email='admin@redimir.cl',
            nombre='Admin General',
            password='admin',
            rol='admin'
        )

    # Creamos un Operador
    if not Usuario.objects.filter(email='operador@redimir.cl').exists():
        op = Usuario(
            email='operador@redimir.cl',
            nombre='Operador de Terreno',
            rol='operador',
            empresa=empresa
        )
        op.set_password('operador123')
        op.save()

    # Creamos un Cliente Corporativo
    if not Usuario.objects.filter(email='cliente@redimir.cl').exists():
        cli = Usuario(
            email='cliente@redimir.cl',
            nombre='Cliente Corporativo',
            rol='cliente',
            empresa=empresa
        )
        cli.set_password('cliente123')
        cli.save()
        
    print("Base de datos alimentada con éxito.")

if __name__ == '__main__':
    run_seed()
