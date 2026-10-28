# ADR-0006 · Nada entra en Business Central sin un OK humano

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

Un pedido mal leído que llega a producción o a facturación cuesta más que el
tiempo que ahorra la automatización. Y la persona que hoy teclea los pedidos no
desaparece: pasa de teclear a revisar.

## Decisión

Ningún documento generado por el pipeline ni por un agente de Business Central se
**registra** sin que una persona lo valide. El pipeline escribe documentos **sin
registrar**. Los agentes de Business Central se configuran con revisión obligatoria.

Al principio, **todo** pasa por la cola, incluso lo de confianza alta. Saltarse la
cola por confianza es una decisión de la empresa con historial delante, no un
parámetro del sistema.

## Consecuencias

- La cola de revisión es un componente de primera, no un extra.
- Cada corrección humana se guarda como ejemplo para la siguiente vez, y ese
  aprendizaje se queda en la empresa.
- Las métricas que importan son las de la cola: tiempo hasta el OK, campos
  corregidos y rechazos.
