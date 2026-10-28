# ADR-0007 · Hacer, y en local, antes que comprar

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

Hay proveedores comerciales que resuelven la captura de pedidos y documentos como
servicio: Rossum, Esker, Conexiom, Workist, Hypatos, ABBYY, Nanonets, Go
Autonomous, virtualworkforce.ai.

Lo que dicen de sí mismos (cifras de sus webs, en septiembre de 2026; son parte
interesada):

| Proveedor | Lo relevante | Lo que no encaja |
|---|---|---|
| **Rossum** | Conector nativo a Business Central. Datos en Frankfurt. Lee manuscrito | Desde 18.000 $ al año, mínimo un año. Sin versión local; single-tenant a presupuesto. Nada para NAV |
| **Esker** | El más completo en canales: fax, correo, EDI, portal, móvil. Francesa | Por presupuesto. Datos en su SaaS. Integración a medida con NAV |
| **Conexiom** | Fuerte en fabricación y distribución | Por presupuesto. BC/NAV no confirmados. Datos en su SaaS |
| **ABBYY Vantage** | Local o nube privada disponibles | Contrato empresarial "de cinco cifras anuales" |
| Resto | | Integración con NAV/BC no documentada o datos fuera de la UE |

Ninguno escribe en **NAV en servidor propio** sin integración a medida. Ninguno
cubre la voz. Todos guardan los documentos en su servicio, salvo en modalidades
caras.

## Decisión

**Hacer, y en local.** Piezas de código abierto con licencia permisiva (Docling MIT,
PaddleOCR Apache-2.0, Whisper MIT, Pydantic MIT), en una máquina dentro de la
empresa, con código propio para encadenarlas y para la bandeja. Comprar solo si
hacer no llega. Nube solo si lo local no llega.

## Por qué

- El documento no sale del edificio. Un SaaS lo contradice de raíz, y su versión
  single-tenant o local cuesta lo que costaría hacerlo.
- La integración con NAV hay que hacerla de todas formas. Lo que se compraría es
  solo la extracción, y ahí el código abierto ya compite.
- Cada corrección humana se queda en la empresa como ejemplo. Con un SaaS, ese
  aprendizaje es del proveedor.
- Coste: una máquina, una vez, frente a 18.000 $ al año como suelo.

## Lo que haría cambiar la decisión

- Que con documentos reales la extracción propia falle y un proveedor lo resuelva en
  la misma prueba. Rossum single-tenant sería el candidato a probar en paralelo.
- Que el volumen o los canales (EDI, fax) crezcan hasta donde Esker tiene sentido.

## Consecuencias

- El mantenimiento es propio. Se acota: pocas piezas, cada una reemplazable, sin una
  plataforma de flujos encima.
- Hay que dimensionar y colocar una máquina, con GPU.
- Cualquier propuesta lleva esta comparación hecha, porque la pregunta "¿por qué no
  compráis?" llega siempre.
