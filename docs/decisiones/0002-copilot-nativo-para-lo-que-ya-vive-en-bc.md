# ADR-0002 · Lo nativo de Business Central antes que desarrollar

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

Business Central online trae Sales Order Agent, E-Documents con lectura de PDF,
emparejado con Copilot y Analysis Assist. Cubren buena parte de la entrada de
pedidos y facturas, siempre que el documento de entrada sea razonable.

## Decisión

Para cada problema, primero se prueba lo que Business Central trae. Solo lo que no
resuelve va al pipeline propio. La regla: **si el documento lo entiende Copilot, no
se toca**.

## Alternativas descartadas

- **Pipeline para todo.** Más control, pero se mantiene a mano lo que Microsoft ya
  mantiene, y la empresa tiene que confiar en una pieza más.
- **Copilot para todo.** No entiende papel torcido escrito a boli, ni el Excel de
  cada comercial, ni una nota de voz. Ahí no llega.

## Consecuencias

- Hay que **verificar licencia, región y disponibilidad** de cada capacidad antes de
  prometerla.
- Hay que **probar con documentos reales** qué porcentaje entiende el agente, en la
  fase de entender el negocio y con muestras que nunca se suben a un repositorio.
- La frontera entre lo nativo y el pipeline se ajusta con datos, no en el diseño.
