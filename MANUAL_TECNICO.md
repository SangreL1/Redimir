# 🛠️ MANUAL TÉCNICO DE ARQUITECTURA & DESPLIEGUE — REDIMIR

Este documento especifica la estructura técnica, componentes de software, modelos de datos y procedimientos de despliegue de la plataforma **Redimir**.

---

## 🏗️ 1. TECNOLOGÍAS Y ESTRUCTURA DE ARQUITECTURA

* **Framework Principal:** Django 4.2+ (Python 3.10+)
* **Base de Datos:** SQLite en desarrollo / PostgreSQL en producción.
* **Librerías Clave:**
  * `reportlab`: Generación programática de Certificados en PDF.
  * `qrcode`: Generación dinámica de códigos QR en imagen PNG.
  * `openpyxl`: Generación y exportación de reportes de Cierre Mensual en Excel (.xlsx).
  * `Pillow`: Manejo y optimización de evidencias fotográficas.

---

## 📂 2. ESTRUCTURA DE APLICACIONES (APPS)

```
Redimir/
├── apps/
│   ├── usuarios/        # Autenticación RUT, Perfiles, Roles (Gerencia, Admin, Operador, Empresa), AuditLog
│   ├── empresas/        # Empresas, Solicitudes de Recolección, Estados de Pago Internos (EDP)
│   ├── servicios/       # Módulos RSD, RESCON/Escombros, Reciclables (11 estados de flujo)
│   ├── calculadora/     # Factores de Eco-equivalencia configurables en BD
│   ├── certificados/    # Emisión PDF, QR Code & Verificación pública (/verificar/<codigo>/)
│   ├── dashboard/       # KPI Admin/Operador, Cierre Mensual & Paquete Documental ZIP
│   ├── lotes/           # Gestión y trazabilidad de lotes de residuos
│   └── notificaciones/ # Sistema asíncrono de alertas internas
├── templates/           # Plantillas HTML5 responsivas con Design System Redimir
├── static/              # Estilos CSS, scripts JS e íconos
└── media/               # Fotos de evidencias y certificados PDF guardados cronológicamente
```

---

## 📊 3. ESQUEMA DE BASE DE DATOS Y AUDITORÍA

### Auditoría de Trazabilidad (`audit_logs`)
Registra cada evento crítico del sistema mediante `AuditLog.registrar(...)`:
- `usuario`: ID del usuario ejecutor.
- `accion`: `creacion`, `modificacion`, `eliminacion`, `validacion`, `emision_doc`.
- `modelo`: Entidad afectada (`Servicio`, `Certificado`, `EstadoDePago`, `Usuario`).
- `registro_id`: Folio o identificador primario.
- `detalles`: Resumen en texto de los cambios efectuados.

---

## 🚀 4. INSTRUCCIONES DE DESPLIEGUE (PythonAnywhere / VPS)

### Paso 1: Clonar el repositorio e instalar dependencias
```bash
git clone <repositorio-redimir>
cd Redimir
python -m venv venv
source venv/bin/activate  # En Linux / Mac
pip install -r requirements.txt
```

### Paso 2: Ejecutar Migraciones
```bash
python manage.py makemigrations
python manage.py migrate
```

### Paso 3: Poblar Factores Eco-Equivalencia Iniciales
```bash
python manage.py shell -c "from apps.calculadora.models import poblar_factores_defecto; poblar_factores_defecto()"
```

### Paso 4: Crear Superusuario Gerencial
```bash
python manage.py createsuperuser
```

---

*Desarrollado para Redimir — Plataforma de Gestión y Trazabilidad Ambiental*
