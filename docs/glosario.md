# Glosario

| Término | Qué es aquí |
|---|---|
| **Navision / NAV / Business Central (BC)** | El mismo ERP de Microsoft en tres épocas. Muchas empresas siguen en la versión de servidor; el destino es BC online |
| **On-premise** | Instalado en un servidor de la empresa. Es lo que Microsoft deja de soportar |
| **BC online / SaaS** | La versión en la nube de Microsoft. Destino de la migración |
| **Partner (de Microsoft)** | Empresa certificada que hace la migración |
| **Albarán** | Documento que acompaña a la mercancía. Del proveedor al recibir; al cliente al enviar. Se valida contra pedido y factura |
| **Documento no registrado** | En BC, un pedido/recepción/factura creado pero no contabilizado. Se puede corregir. Registrar es el paso irreversible, y lo da una persona |
| **Maestros** | Artículos, clientes, proveedores, tarifas, unidades. Los datos base contra los que se resuelve todo |
| **Referencia de artículo** | En BC, cómo llama un cliente o proveedor concreto a un artículo nuestro. Clave para resolver pedidos |
| **Contra stock / contra pedido** | Sistema de reaprovisionamiento del artículo: se fabrica para tener en almacén o solo cuando hay pedido |
| **Sales Order Agent** | Agente de BC que lee correos de clientes y propone pedidos con revisión humana |
| **E-Documents** | Módulo de BC para recibir facturas electrónicas y PDFs y convertirlos en documentos de compra |
| **Azure Document Intelligence (ADI)** | Servicio de Microsoft de extracción de documentos. Lo usa BC; segunda opción para el pipeline |
| **Docling** | Extractor de documentos de código abierto (IBM). Convierte PDF/imagen/Excel en estructura. Corre en local |
| **Normalización** | Etapa del pipeline que convierte lo extraído en un esquema fijo, siempre el mismo |
| **Resolución** | Etapa que convierte "lo de siempre" en código de artículo, cantidad y unidad consultando BC |
| **Cola de revisión** | Pantalla donde una persona da OK, corrige o rechaza lo que el pipeline propone |
| **API v2.0 / OData** | Formas estándar de leer y escribir en BC desde fuera |
| **SOAP sobre páginas / página 42** | Servicios web del NAV de hoy. La página 42 es la de pedidos de venta. Lo que usa el adaptador NAV |
| **Adaptador de escritura** | La etapa del pipeline que habla con el ERP. Dos versiones: NAV hoy, BC mañana |
| **Copilot Credits** | Cómo Microsoft cobra los agentes de BC: por uso, a 0,01 $ el crédito, aparte de la licencia |
| **Touchless** | Documento que pasó por la bandeja sin que nadie corrigiera nada |
| **AL** | Lenguaje de extensiones de BC. "Picar dentro" |
| **Entra ID** | Identidad de Microsoft (antes Azure AD). Con lo que se autentica el pipeline |
| **Carril 0 / A / B** | Maestros / lo nativo de BC / el pipeline propio |
| **DPO** | Delegado de protección de datos |
| **Humano en el loop** | Nada se registra sin OK de una persona |
