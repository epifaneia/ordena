# Ordena · Pedidos sucios → Business Central

*Read this in [English](README.md).*

Un pedido que llega como llegan los pedidos de verdad, un correo a medias o una nota de voz de WhatsApp, entra en Business Central como **pedido de venta sin registrar**, con cliente, artículos, cantidades y fecha resueltos contra los maestros del ERP, lo dudoso marcado y el original adjunto. Una persona lo valida antes de que cuente. Todo en local, salvo el propio Business Central.

> La IA tiene riesgos. El código los acota. La norma responde de lo que queda.

**Prueba de concepto** con los datos de demostración de Microsoft (CRONUS): sin datos de ninguna empresa real.

[Filosofía de diseño](#filosofía-de-diseño) · [Los cinco pasos](#los-cinco-pasos-en-este-proyecto) · [Probarlo](#probarlo) · [Decisiones de diseño](#decisiones-de-diseño) · [Limitaciones](#limitaciones) · [Seguridad y regulación](#seguridad-y-regulación)

---

## Filosofía de diseño

Cualquier aplicación con IA tiene cinco pasos. Solo el paso 4 invoca un modelo; los otros cuatro son código: reproducibles, testeables, sin red. El paso 5 nunca corrige: marca y degrada. Texto completo en [epifaneia.dev](https://epifaneia.dev).

```
 1 LIMPIEZA      2 CONTEXTO      3 GUARDARRAÍL IN    4 PROCESO        5 GUARDARRAÍL OUT
 ■ código        ■ código        ■ código            ▲ modelo         ■ código
```

## El escenario

Una empresa industrial mediana con Navision en servidor propio, que tiene que migrar a Business Central online porque Microsoft deja de dar soporte a la versión de servidor. Los comerciales y los clientes mandan los pedidos cada uno a su manera: correos, notas de voz, PDFs, papel. Alguien los teclea a mano en el ERP. La confidencialidad es el primer criterio, y no hay departamento de IT.

## Dónde aporta valor la IA

Entender un mensaje humano: "lo de siempre, pero dos sillas más, y que llegue el jueves", dicho en una nota de voz. Eso es lo único que hace el modelo. Qué cliente es, qué artículo, qué unidad, qué fecha exacta y si el precio cuadra con la tarifa lo decide el código, contra los maestros de Business Central. Y si no está seguro, lo dice.

---

## Los cinco pasos en este proyecto

★ marca dónde está la mejora en este proyecto: la **resolución determinista** y la **escritura sin registrar** en el ERP.

| Paso | Qué hace aquí | |
|---|---|---|
| 1 · Limpieza | `transcribir.py`: Whisper (faster-whisper large-v3-turbo) en local, con el vocabulario de clientes y artículos de los maestros; los segmentos de baja confianza quedan marcados. El texto entra tal cual, con remitente y fecha. | |
| 2 · Contexto | El mensaje, su fecha y el remitente. El modelo no recibe la tarifa ni puede inventar códigos: no los ve. | |
| 3 · Guardarraíl de entrada | `esquema.py`: un esquema cerrado (Pydantic) forzado en la salida del modelo, a temperatura 0. Al modelo se le pide copiar **tal cual** del mensaje (el nombre del cliente, la descripción del artículo, la fecha en palabras) y no inventar códigos. Los modelos pequeños no siempre obedecen: el paso 5 lo comprueba. | |
| 4 · Proceso | Una llamada por mensaje: Ollama en local por defecto (qwen2.5:7b en una GPU de 6 GB). Gemini y Groq existen solo para medir el techo con datos de CRONUS, y hay que pedirlos. | |
| 5 · Guardarraíl de salida | `resolver.py` y `tickets.py`: cliente y artículo se resuelven contra los maestros; si el segundo candidato está a menos de 8 puntos del primero, es **ambiguo** y queda dudoso. Fechas relativas ("el jueves") calculadas desde la fecha del mensaje. Un precio que no cuadra con la tarifa, o que no aparece literalmente en el mensaje, queda dudoso: no se sobrescribe. Igual el cliente, la dirección de entrega y cada descripción de artículo que copió el modelo: si no está en el mensaje (sin contar mayúsculas, tildes, signos ni espacios), queda dudoso con "el modelo no copió literal", sin corregirlo. Una fecha que vuelve ya calculada (`2026-11-02`) y que el mensaje no contiene, también. Un ticket sin los campos obligatorios nace incompleto. `bc.py` crea el pedido **sin registrar**, con el id del ticket como número de documento externo (repetir el mismo mensaje no lo duplica) y adjunta el original comprobando que llega entero. | ★ |

## La bandeja

`python web.py` abre en `http://127.0.0.1:8765` una bandeja con la estética del cliente Windows de Navision 2013. Se arrastra un correo o una nota de voz, el mensaje entra en cola y los tickets aparecen solos, con los campos dudosos en ámbar, la transcripción con los segmentos dudosos resaltados y el audio original.

Los pedidos tienen estado: `pendiente → validado → escrito`, o `rechazado` con motivo. Solo un pedido validado se escribe en el ERP, y una transición no permitida se rechaza. "Abrir en el ERP" lleva al pedido en el cliente web de Business Central.

## Probarlo

Sin modelo y sin Business Central, con una interpretación ya hecha y los maestros de demostración:

```bash
python -m venv .venv && .venv\Scripts\activate          # en Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --interpretacion ejemplos/interpretacion_ejemplo.json --remitente helen.ray@contoso.com
```

Con el modelo local (Ollama arrancado y `ollama pull qwen2.5:7b`):

```bash
python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --remitente helen.ray@contoso.com
python -m ordena_poc.main web
```

`ejemplos/guion_audio.md` trae los guiones de las notas de voz de prueba, con lo que se espera de cada una: grábalas tú, no se suben al repo.

### Contra Business Central de verdad

1. Activa la **prueba gratuita** de Dynamics 365 Business Central en un tenant de Microsoft 365. Crea el entorno `Production` con la empresa CRONUS.
2. **Registra una aplicación** en Entra ID: cuentas de este directorio, *Permitir flujos de cliente público*, permisos delegados de Dynamics 365 Business Central `Financials.ReadWrite.All` y `user_impersonation` con consentimiento de administrador.
3. Copia `.env.example` a `.env` y rellena `BC_TENANT_ID` y `BC_CLIENT_ID`.
4. `python -m ordena_poc.main probar-bc`: la primera vez pide entrar por código de dispositivo.
5. `python -m ordena_poc.main maestros`: descarga clientes y artículos de CRONUS y el vocabulario para Whisper.
6. `python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --remitente helen.ray@contoso.com --crear`, y abre en Business Central el número de pedido que imprime.

Para producción, el mismo código usa credenciales de aplicación (`BC_CLIENT_SECRET`) con un conjunto de permisos escrito a mano, sin permiso de registrar.

## Medido

- **Transcripción en local:** 33 s de audio en unos 11 s en una RTX 2060 (6 GB), 103 s en CPU.
- **De punta a punta contra Business Central:** un mensaje de prueba crea el pedido de venta sin registrar en CRONUS, con las líneas a precio de tarifa del propio ERP; volver a procesar el mismo mensaje no crea un segundo pedido.

Lo que no está medido: la precisión con mensajes reales de una empresa. Es lo primero que se mediría con sus documentos.

---

## Decisiones de diseño

Siete decisiones, cada una con su contexto, sus alternativas descartadas y lo que la haría cambiar, en [docs/decisiones/](docs/decisiones/):

1. [Business Central online como destino, Navision como origen](docs/decisiones/0001-business-central-online-en-vez-de-erp-a-medida.md)
2. [Lo nativo de Business Central antes que desarrollar](docs/decisiones/0002-copilot-nativo-para-lo-que-ya-vive-en-bc.md)
3. [Docling para los documentos sucios](docs/decisiones/0003-docling-para-documentos-sucios.md)
4. [Dónde corre el modelo](docs/decisiones/0004-donde-corre-el-modelo.md)
5. [API estándar antes que extensión AL](docs/decisiones/0005-api-estandar-antes-que-extension-al.md)
6. [Nada entra en Business Central sin un OK humano](docs/decisiones/0006-humano-en-el-loop-siempre.md)
7. [Hacer, y en local, antes que comprar](docs/decisiones/0007-hacer-y-local-antes-que-comprar.md)

Más [los puntos de contacto con Business Central](docs/arquitectura/business-central.md), [los datos maestros](docs/arquitectura/datos-maestros.md) y un [glosario](docs/glosario.md). Los documentos de diseño están en español.

## Limitaciones

- Prueba de concepto sobre datos de demostración. Ningún mensaje real; la precisión con el correo y las notas de voz de una empresa está sin medir.
- Solo Business Central online. El adaptador de Navision en servidor (SOAP sobre la página 42) está diseñado y no escrito.
- Solo texto y voz. PDF, Excel y papel escaneado pasarían por Docling ([ADR-0003](docs/decisiones/0003-docling-para-documentos-sucios.md)), que no está conectado.
- La bandeja no une ni parte tickets, no manda acuse de recibo ni borrador de preguntas al cliente, no tiene roles ni búsqueda, y no consulta el histórico del cliente ("lo de siempre" queda dudoso).
- Pocos tests automáticos: `tests/test_tickets.py` cubre la comprobación de literalidad y parte del resolver, sin red. El contacto y las observaciones no se comprueban contra el mensaje. No hay registro de custodia (quién lanzó qué, qué salió de la máquina). Es lo siguiente.

---

## Seguridad y regulación

Los mismos cuatro epígrafes que en el resto de repositorios. Las filas **hoy** son lo que hace el código; las filas **siguiente**, lo que falta.

| | | |
|---|---|---|
| **Confidencialidad** | Transcripción y modelo en local por defecto: el mensaje no sale de la máquina. La nube solo se usa si se pide (`--llm gemini`, `--stt groq`) y está pensada para comparar con los datos de demostración, nunca con datos de una empresa. `.env`, tokens, audios y la bandeja están fuera de git. | **hoy** |
| **Trazabilidad** | Cada ejecución deja en `salida/` el mensaje, la transcripción, la salida cruda del modelo y los tickets. En la bandeja, cada ticket guarda su original, su historial de estados y el número del pedido que creó; en Business Central, el pedido lleva el id del ticket como documento externo y el original adjunto. | **hoy** |
| | Registro de custodia por llamada al modelo (actor, paso, si el dato salió de la máquina, hash de la entrada), como en el resto de repositorios. | **siguiente** |
| **Prevención de fugas** | Autenticación con Microsoft Entra ID: código de dispositivo para probar y credenciales de aplicación para producción. Ni usuario y contraseña ni claves de servicio web en el código. Los permisos de la aplicación se acotan en Business Central, con un conjunto escrito a mano y sin permiso de registrar. | **hoy** |
| **Humano en el bucle** | El pipeline solo escribe pedidos **sin registrar**. En la bandeja, solo los que una persona ha validado; la línea de comandos (`procesar --crear`) escribe sin pasar por ella, para probar la integración, y se queda en la prueba de concepto. Lo dudoso va marcado en ámbar con su motivo; nada se corrige en silencio. Registrar el pedido, el paso irreversible, lo hace siempre una persona en Business Central. | **hoy** |

Escrito con referencia al EU AI Act (2024/1689), el RGPD e ISO/IEC 27001. No se declara ninguna certificación ni conformidad: la tabla dice qué parte cubre el código y qué parte es de la empresa.

---

## Estructura

```
ordena_poc/   esquema · transcribir · interpretar · maestros · resolver · tickets · bc · bandeja · mostrar · main
ordena_poc/web/   la bandeja (FastAPI y una página con la estética de Navision 2013)
data/         maestros_demo.json: una aproximación a CRONUS para trabajar sin conexión
ejemplos/     pedidos de prueba, una interpretación hecha y el guion de las notas de voz
tests/        test_tickets.py: sin red y sin modelo (python tests/test_tickets.py)
docs/         decisiones/ (siete ADR) · arquitectura/ · glosario
```

Daniel Martín · [epifaneia.dev](https://epifaneia.dev) · Apache-2.0
