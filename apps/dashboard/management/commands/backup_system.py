"""
Comando personalizado de respaldo para la plataforma Redimir.
Ejecución: python manage.py backup_system
Punto 24 del Checklist Maestro Redimir.
"""
import os
import zipfile
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone


class Command(BaseCommand):
    help = 'Genera un respaldo comprimido ZIP de la base de datos y la carpeta media/ de Redimir.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Iniciando proceso de respaldo del sistema Redimir...'))

        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"backup_redimir_{timestamp}.zip"
        zip_filepath = os.path.join(backup_dir, filename)

        try:
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED) as zf:
                # 1. Respaldar Base de Datos SQLite
                db_path = os.path.join(settings.BASE_DIR, 'db.sqlite3')
                if os.path.exists(db_path):
                    zf.write(db_path, 'database/db.sqlite3')
                    self.stdout.write(self.style.SUCCESS('  [+] Base de datos respaldada correctamente.'))

                # 2. Respaldar carpeta media
                media_root = settings.MEDIA_ROOT
                if os.path.exists(media_root):
                    for root, dirs, files in os.walk(media_root):
                        for f in files:
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, media_root)
                            zf.write(full_path, os.path.join('media', rel_path))
                    self.stdout.write(self.style.SUCCESS('  [+] Archivos multimedia (media/) respaldados correctamente.'))

            size_mb = os.path.getsize(zip_filepath) / (1024 * 1024)
            self.stdout.write(self.style.SUCCESS(f"RESPALDO COMPLETADO EXITOSAMENTE: {zip_filepath} ({size_mb:.2f} MB)"))

            # Registrar en AuditLog si existe
            try:
                from apps.usuarios.models import AuditLog
                AuditLog.registrar(
                    usuario=None,
                    accion='configuracion',
                    modelo='Sistema',
                    registro_id='BACKUP',
                    campo='copia_seguridad',
                    valor_nuevo=filename,
                    detalles=f"Respaldo automático del sistema realizado exitosamente. Archivo: {filename} ({size_mb:.2f} MB)"
                )
            except Exception:
                pass

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error al generar el respaldo: {e}"))
