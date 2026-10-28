# ADR-0003 · Docling para la extracción de documentos sucios

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

Lo que llega de fuera es papel escaneado, fotos, PDFs con el formato de cada
cliente y Excel. Hace falta convertirlo en estructura (texto, tablas, posición)
antes de que un modelo lo interprete. El criterio es que los documentos no salgan a
servicios de terceros: hacer, y en local.

## Decisión

Docling (IBM, licencia MIT) como extractor por defecto, en una máquina dentro de la
empresa. Viable en CPU y fuerte en tablas, que es lo que son albaranes y pedidos.

## Alternativas

| Opción | Licencia | Veredicto |
|---|---|---|
| **PaddleOCR-VL** | Apache-2.0 | Mejor precisión publicada en escaneos torcidos y multilingüe. Necesita GPU. **Segunda opción** para el papel malo |
| **Granite-Docling** (IBM, 258M) | Apache-2.0 | Compacto, un solo paso. Candidato si hace falta aligerar |
| **Azure Document Intelligence en contenedor** | Comercial | Corre dentro de la empresa. Es lo que usa Business Central para E-Documents. Para PDFs limpios de facturas |
| **Mistral OCR en contenedor** | Comercial | Empresa francesa, contenedor autogestionado. Misma función que la anterior |
| DeepSeek-OCR | MIT | Mucho rendimiento, menor precisión. No hace falta al volumen de una mediana empresa |
| MinerU | AGPL | Copyleft. Descartado |
| Servicios OCR de terceros en SaaS | | Los documentos salen. Descartado |
| Modelo multimodal directamente sobre la imagen | | Se salta la estructura; peor con tablas largas. Útil solo como complemento para anotaciones a boli |
| Tesseract + reglas | Apache-2.0 | Sin tablas ni maquetación. Se queda corto |

## Consecuencias

- Hace falta una máquina en la empresa. Sin GPU para Docling; con GPU si entran
  PaddleOCR-VL o el modelo local de normalización, que es lo probable. Se dimensiona
  una vez.
- Hay que probar con los escaneos reales. Un escáner torcido a 150 dpi no es un PDF
  generado.
- Docling es reemplazable: el esquema de salida de la normalización es propio y no
  depende del extractor.
- Esta prueba de concepto todavía no usa Docling: trabaja con texto y notas de voz.
