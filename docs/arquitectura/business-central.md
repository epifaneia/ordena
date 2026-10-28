# Puntos de contacto con Business Central

Lo que hay que saber de Navision y Business Central para diseñar lo que va
alrededor. Lo marcado **(verificar)** hay que contrastarlo con la documentación
de Microsoft y con el partner de migración de cada empresa.

## Navision, NAV, Business Central: qué es cada cosa

- **Navision** es el nombre de siempre. Microsoft lo llamó **Dynamics NAV**
  hasta 2018 y desde entonces **Dynamics 365 Business Central** (BC).
- "Navision en un servidor" suele ser NAV 2018 o anterior, o BC on-premise.
  La versión exacta cambia mucho el camino de migración:
  - BC on-premise reciente → herramienta de migración a cloud de Microsoft,
    directa.
  - NAV 2018 o anterior → muy probablemente upgrade técnico intermedio, o
    migración de datos por paquetes de configuración. Lo hace un partner.
- Fin del soporte extendido: NAV 2018, 11 de enero de 2028; NAV 2017, 11 de
  enero de 2027; NAV 2016 terminó el 14 de abril de 2026.

## Cómo se habla con el Navision de hoy

No hace falta esperar a la nube. NAV 2013 a 2018 exponen **servicios web**:

| Vía | Qué permite | Notas |
|---|---|---|
| **SOAP sobre páginas** | Crear, leer, modificar y borrar sobre cualquier página publicada como servicio web. La página 42 (Sales Order) es la de pedidos de venta | Puerto 7047 por defecto. En NAV 2016 crear un pedido con líneas son varias llamadas: cabecera y luego cada línea |
| **OData** | Lectura de páginas y consultas publicadas | Para leer maestros (artículos, clientes, referencias, tarifas) |

Requiere que alguien publique las páginas como servicio web en el NAV y que
el pipeline llegue al servidor por la red interna. Autenticación: la que
tenga configurada ese NAV (Windows o NavUserPassword).

Esto es lo que usa el adaptador de escritura hasta la migración. Ver
[ADR-0001](../decisiones/0001-business-central-online-en-vez-de-erp-a-medida.md).

## Cómo se habla con BC online

| Vía | Para qué la usaríamos | Notas |
|---|---|---|
| **API v2.0** (REST, OData v4) | Leer maestros (artículos, clientes, proveedores, tarifas), crear pedidos de venta, pedidos de compra, facturas de compra. Todo en estado no registrado | Estándar, versionada, documentada. Primera opción siempre |
| **OData sobre páginas/consultas** | Cuando la API v2.0 no expone un campo (por ejemplo, campos de fabricación del artículo) | Depende de la página; más frágil entre versiones |
| **API custom en AL** | Cuando ninguna de las anteriores llega: exponer exactamente la entidad que el pipeline necesita, o una tabla de staging propia | Requiere una extensión AL desplegada en el tenant. Es "picar dentro de BC" |
| **Webhooks** (subscriptions) | Enterarse de cambios en BC sin sondear: pedido registrado, artículo modificado | Para trazabilidad y para cerrar el loop |
| **Power Automate / Dataverse** | Alternativa low-code para captura de correo y disparadores | Útil si alguien de la empresa sin perfil de programador tiene que poder tocar algo |
| **Servidor MCP de BC** | Existe desde 2026 wave 1 (BC28): acceso por MCP para agentes externos | Simplifica la resolución contra maestros desde el pipeline. Verificar si está en la licencia |

Autenticación: **Microsoft Entra ID** (OAuth 2.0), con una aplicación
registrada en el tenant de la empresa y permisos acotados. Nada de usuario/contraseña ni
claves de servicio web.

## Lo que BC trae de serie y que nos ahorra trabajo

Todo esto corre dentro del servicio de Microsoft, con Azure OpenAI, sin que
los datos salgan del límite de datos de la UE y sin usarse para entrenar.
**Solo en BC online**: nada de esto
existe en NAV ni en BC on-premise.

**Lo que cuesta.** El Copilot básico (chat, resúmenes, Analysis Assist) va
incluido en Essentials y Premium. **Los agentes no**: se pagan por uso con
Copilot Credits, a 0,01 $ el crédito vía suscripción Azure (pack prepago
algo más barato). Órdenes de magnitud de la documentación de Microsoft:

| Agente | Consumo |
|---|---|
| Sales Order Agent | Ejemplo de Microsoft: 100 solicitudes al mes, unos 1.650 créditos, es decir unos 16,50 $ |
| Payables Agent | 5 créditos por línea de factura, 0,05 $ |
| Expense Agent | 50 créditos por recibo |

Barato al volumen de una mediana empresa, pero es **coste variable** y va aparte.
Microsoft ajusta los créditos por acción; revisar cada trimestre.

| Capacidad | Qué hace | Dolor que cubre |
|---|---|---|
| **Sales Order Agent** (GA) | Vigila un buzón de Microsoft 365, lee asunto, cuerpo y adjuntos PDF o imagen, identifica al cliente por su correo, busca artículos en artículos, variantes, referencias, atributos, categorías y traducciones, comprueba disponibilidad, propone presupuesto, mantiene la conversación por correo. Una persona revisa siempre lo que sale | Pedidos "de cualquier manera" cuando vienen por correo. **No** cubre voz, papel que no llegue por correo, EDI ni portal |
| **E-Documents** | Recibe facturas electrónicas (Peppol, correo) y PDFs; con Document Intelligence saca cabecera y líneas; crea borrador de factura de compra | Facturas de proveedor |
| **Emparejado con Copilot** | Casa líneas del e-documento con líneas del pedido de compra | Validación factura ↔ pedido |
| **Payables Agent** | Lee facturas de proveedor entrantes, las casa con proveedor y cuentas, prepara borrador para aprobación | Financiero |
| **Expense Agent** (2026 wave 1) | Recibos de gastos | Fuera de alcance, se anota |
| **Analysis Assist** | Análisis de listas con lenguaje natural, pivotes | Los "demasiados informes" |
| **Chat with Copilot** | Preguntas sobre sus datos y sobre cómo hacer cosas en BC | Formación, adopción |
| **Copilot Toolkit (AL)** | Para construir nuestra propia experiencia Copilot dentro de BC con Azure OpenAI | Solo si queremos que la cola de revisión viva dentro de BC |

**Fabricación** (contra stock / contra pedido, planificación) es de la licencia
**Premium**. Quien use hoy el planificador necesitará Premium en la nube.

## Qué preguntarle al partner de migración

- Versión exacta actual y camino de migración que proponen.
- Qué páginas tienen ya publicadas como servicio web y quién puede publicar
  más (para el adaptador NAV).
- Si tienen personalizaciones (objetos modificados) en el Navision actual.
  Cada una es un punto de fricción en la migración y una oportunidad de
  quitarla si BC ya lo hace.
- Qué extensiones de terceros hay instaladas.
- Región del datacenter (debería ser UE).
- Quién administra el tenant de Microsoft 365 y si ya hay Entra ID.

## Decisión pendiente: ¿extensión AL o todo desde fuera?

Preferencia: **todo desde fuera por API estándar** mientras se pueda. Razones:
sin IT interno, cada extensión AL es una cosa más que actualizar con cada
versión de BC. Se abre la puerta a AL solo para dos cosas:

1. Una **tabla de staging** con el documento origen adjunto, si la cola de
   revisión se quiere dentro de BC.
2. Exponer campos que la API estándar no da.

Ver [ADR-0005](../decisiones/0005-api-estandar-antes-que-extension-al.md).
