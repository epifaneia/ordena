# ADR-0001 · Business Central online como destino, Navision como origen

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

El escenario de diseño (ver el [README](../../README.md)): una empresa industrial
mediana con Navision en servidor propio, sin departamento de IT, para la que la
confidencialidad es el primer criterio y que tiene que migrar a la nube de todas
formas, porque Microsoft deja de dar soporte a la versión de servidor.

Ante un ERP que se queda corto siempre aparece la tentación de quitarlo y poner un
sistema propio sobre el que aplicar IA. Cambiar de ERP es caro y arriesgado, y aquí
se sumaría a una migración que ya es obligatoria.

Un dato cambia el diseño: **NAV 2013 a 2018 ya exponen servicios web SOAP y
OData** sobre sus páginas, incluida la de pedidos de venta (página 42). Se pueden
crear pedidos desde fuera hoy, sin esperar a la nube. Los plazos de soporte
extendido: NAV 2016 terminó en abril de 2026, NAV 2017 termina en enero de 2027 y
NAV 2018 en enero de 2028.

## Decisión

Business Central online es el destino y será la única fuente de verdad. Lo que se
diseña es lo que va alrededor. No se propone un ERP a medida.

**El pipeline escribe en Navision desde el día uno** por SOAP/OData y, tras la
migración, en Business Central por la API v2.0. La etapa de escritura es un
adaptador con dos implementaciones. Para las personas es un solo cambio: la bandeja
no cambia porque cambie el ERP de debajo. Esta prueba de concepto implementa el
adaptador de Business Central.

## Alternativas descartadas

- **ERP a medida ahora.** Dos cambios en vez de uno, y se pierden Copilot, los
  agentes y E-Documents, que vienen hechos.
- **Esperar a la migración para escribir en el ERP.** Con NAV 2018 hay soporte hasta
  2028. Dos años sin entregar nada no es un plan.
- **Otro ERP en la nube.** No hay motivo: Navision ya se conoce, hay partners y hay
  un camino de migración oficial.

## Consecuencias

- Hace falta saber la **versión exacta de NAV**: fija qué servicios web hay, cuántas
  llamadas SOAP cuesta un pedido con líneas y cuánto soporte queda.
- El adaptador de NAV se tira tras la migración. Es trabajo que caduca, así que se
  acota: crear pedido de venta y recepción de compra, nada más.
- El valor está en el dato sucio que llega de fuera y en los maestros, no en
  reescribir lo que Business Central ya hace.
