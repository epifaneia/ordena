# ADR-0004 · Dónde corre el modelo de normalización

**Estado:** aceptada para la prueba de concepto. Fecha: 2026-09-05.

## Contexto

La etapa de normalización necesita un modelo de lenguaje que convierta el mensaje o
la salida de la extracción en el esquema cerrado. Ese modelo ve nombres de
clientes, artículos y precios.

El primer criterio de la empresa es la confidencialidad, y el criterio de diseño es
hacer, y en local.

## Decisión

**Modelo local** en la máquina del pipeline, dentro de la empresa. Azure OpenAI en
el tenant de la propia empresa queda como alternativa solo si la prueba con
documentos reales demuestra que el modelo local no da la calidad.

## Comparativa

| | Modelo local | Azure OpenAI en el tenant de la empresa |
|---|---|---|
| Datos | No salen de la máquina | Suscripción propia, región UE, sin entrenar con ellos |
| Calidad | Suficiente para un esquema cerrado con un modelo mediano; hay que medirlo | Alta desde el primer día |
| Coste | Una máquina con GPU, una vez | Por uso, bajo |
| Mantenimiento | Actualizar el modelo de vez en cuando | Ninguno |
| Qué se puede decir de los datos | "No salen del edificio" | "Dentro de Microsoft, como el ERP" |
| Sirve después para datos más sensibles (I+D) | Sí, la misma máquina o una igual | No: para eso habría que montar local igualmente |

## Lo que haría cambiar la decisión

- Que con documentos reales el modelo local falle en campos críticos y no se arregle
  con ejemplos ni con un modelo mayor.
- Que la empresa no quiera una máquina con GPU. Entonces, Azure en su tenant, y se
  explica la diferencia.

## Consecuencias

- La etapa de modelo es **intercambiable**: misma entrada, mismo esquema de salida,
  varias implementaciones. En esta prueba de concepto, Ollama por defecto; Gemini y
  Groq existen solo para medir el techo con los datos de demostración de Microsoft,
  y hay que pedirlos de forma explícita.
- La máquina se dimensiona con GPU desde el principio.
- La prueba con documentos reales incluye esta comparación con números.
