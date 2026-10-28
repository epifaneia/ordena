# ADR-0005 · API estándar de Business Central antes que extensión AL

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

Hay dos formas de que el pipeline hable con Business Central: desde fuera, por la
API estándar (v2.0, OData), o desde dentro, con una extensión AL que exponga
exactamente lo necesario y pueda alojar la cola de revisión.

Sin IT interno, cada extensión AL es algo más que mantener con cada actualización de
Business Central (dos al año).

## Decisión

Todo desde fuera por la API estándar mientras alcance. Extensión AL solo si:

1. Se quiere la cola de revisión dentro de Business Central (la misma pantalla que ya
   se usa, con el documento adjunto al registro), o
2. La API estándar no expone un campo imprescindible.

## Alternativas descartadas

- **Extensión AL desde el principio.** Más integrada, pero es programar dentro de un
  sistema con un ciclo de actualización que no se controla.
- **Power Automate para toda la integración.** Válido para captura y disparadores;
  insuficiente para la resolución y la cola.
- **Label Studio Community como cola de revisión.** Apache-2.0 y sin coste, pero es
  una herramienta de etiquetado: la colaboración multiusuario es de pago, y la
  pantalla necesaria (el documento al lado y tres botones) es más simple.
- **n8n como orquestador y cola.** Su licencia obliga a que corra en la
  infraestructura de la empresa, y sin IT interno es una plataforma más que nadie
  mantendrá.

## Nota sobre NAV

Antes de la migración, la "API estándar" es SOAP/OData de NAV. El mismo principio:
publicar páginas existentes como servicio web antes que tocar objetos de NAV, que
además complicarían la migración.

## Consecuencias

- La cola de revisión nace como web mínima fuera de Business Central: es la bandeja
  de esta prueba de concepto. Si se quiere dentro, se evalúa AL más adelante.
- Comprobado en la prueba de concepto: la API v2.0 crea pedidos de venta sin
  registrar, con número de documento externo y el original adjunto. Queda por
  confirmar lo mismo para recepciones y facturas de compra, y la lectura de
  referencias de artículo por tercero.
