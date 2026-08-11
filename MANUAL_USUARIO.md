# 📖 MANUAL DE USUARIO — PLATAFORMA REDIMIR

Bienvenido al **Manual Oficial de Usuario** de la plataforma de trazabilidad de residuos **Redimir**.

---

## 👥 ROLES Y ACCESOS DEL SISTEMA

La plataforma soporta 4 perfiles principales de usuario:

1. **Gerencia / Superadmin:**
   * Acceso total a todos los módulos y reportes gerenciales.
   * Gestión de usuarios y asignación de roles.
   * Visualización y emisión de **Estados de Pago Internos** con información tarifaria.
   * Acceso al **Historial de Auditoría & Trazabilidad**.
   * Ajuste de **Factores de Eco-equivalencia**.

2. **Administrador Redimir:**
   * Programación y creación de solicitudes de retiro.
   * Asignación de operadores a solicitudes.
   * **Validación de Registros de Terreno** (Aprobación u Observación con comentarios).
   * Emisión de **Certificados Oficiales con Código QR**.
   * Generación de **Cierres Mensuales** y paquetes `.ZIP`.

3. **Operador / Recolector (Mobile-First):**
   * Panel táctil optimizado para uso en terreno bajo luz solar.
   * Visualización de retiros asignados para hoy.
   * Registro de retiros por módulo (**RSD**, **RESCON/Escombros**, **Reciclables**).
   * Subida de tickets externos y captura de **múltiples fotografías con previsualización interactiva**.
   * Captura automática de **Coordenadas GPS**.

4. **Cliente / Empresa:**
   * Portal exclusivo de la empresa.
   * Envío de nuevas **Solicitudes de Recolección**.
   * Trazabilidad en tiempo real del estado de cada retiro.
   * Descarga de **Certificados y Reportes de Impacto Ambiental**.

---

## 🚛 FLUJO DE OPERACIÓN Y RETIROS

El ciclo de vida de cada retiro pasa por las siguientes etapas:

1. **Solicitud / Programación:**
   * El cliente o el admin crea la solicitud de recolección.
2. **Asignación & En Ruta:**
   * El operador acepta el servicio o le es asignado por la administración.
3. **Registro en Terreno (Operador):**
   * El operador ingresa a la app móvil, captura las fotos del ticket o guía, ingresa la cantidad (kg / m³) y presiona enviar.
4. **Validación (Admin):**
   * El administrador revisa el ticket y las fotos en `/validaciones/`. Si todo está correcto, presiona **Validar**. Si hay discrepancias, marca como **Observado**.
5. **Emisión de Certificados & Cierre:**
   * Con los registros validados, se emiten los certificados en PDF con **código QR de verificación pública** y se empaqueta el cierre mensual en formato ZIP o Excel.

---

## 🔐 VERIFICACIÓN PÚBLICA DE CERTIFICADOS CON QR

Cada certificado PDF emitido incluye un **Código QR único y un Folio oficial** (`CERT-YYYYMMDD-XXX`). 

Para comprobar la validez legal de cualquier documento:
1. Escanee el código QR impreso en el PDF con la cámara de su teléfono móvil.
2. La plataforma desplegará la pantalla oficial de **Verificación de Autenticidad** confirmando la razón social de la empresa, el período verificado, el desglose de kg retirados y el sello digital de Redimir.

---

*Redimir — Trazabilidad & Gestión Sustentable de Residuos*
