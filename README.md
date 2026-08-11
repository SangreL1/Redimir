# SISTEMA REDIMIR
Plataforma Web de Trazabilidad y Gestión de Residuos Reciclables

## Stack Tecnológico 
* **Backend:** Django 4.2 / Django REST Framework
* **Frontend:** Bootstrap 5, Chart.js, Vanilla JS (Fetch)
* **Auth:** Json Web Token (JWT)
* **PDF Engine:** ReportLab

## Requisitos y Setup Local
1. Ingresa a la carpeta del proyecto.
2. Activa tu entorno virtual previamente instalado y migrado:
```powershell
.\venv\Scripts\activate
```

3. Crea un usuario administrador para visualizar el portal de control general:
```powershell
python manage.py createsuperuser
```

4. Posteriormente, puedes correr el servidor web del sistema con el siguiente comando:
```powershell
python manage.py runserver
```

## Estructura de Aplicaciones Desarrolladas
* **usuarios:** Autenticación (JWT Tokens) y asignación de roles.
* **empresas:** Entidades Corporativas / Puntos Verdes.
* **lotes:** Engine core de trazabilidad general. Flujo y estados de recolectado a procesado.
* **eventos:** Historial continuo del ciclo de vida que se automatizan según el Lote.
* **certificados:** Conversor e historial de PDFs formales trazables listos para su descarga corporativa.
* **dashboard:** Portal interactivo para visualización de KPIs gerenciales y de Clientes.
