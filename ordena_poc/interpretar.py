"""Interpretación con salida forzada al esquema cerrado.

Tres proveedores con el mismo prompt y el mismo esquema, para poder comparar:
- ollama: modelo local (lo que correría dentro de la empresa);
- gemini y groq: nube, solo como techo de comparación con datos de CRONUS.

El modelo copia lo que ve. No inventa códigos: resolver es la etapa siguiente.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import requests

from .config import cfg
from .esquema import Interpretacion

SISTEMA = """Eres el intérprete de Ordena, un sistema que convierte mensajes de clientes en tickets para una empresa que fabrica y vende.
Recibes UN mensaje (correo, texto o transcripción de una nota de voz) y devuelves SOLO un JSON que cumple el esquema.

Reglas:
1. Un mensaje puede contener UNA, VARIAS o NINGUNA petición. Cada petición va aparte en `peticiones`.
2. Tipos: pedido (pide mercancía), modificacion (cambia o cancela un pedido anterior), consulta (pregunta: precio, plazo, estado), queja, comentario (sin acción), ruido (publicidad, fuera de oficina, nada que ver).
2b. Saludos, despedidas, agradecimientos y fórmulas de cortesía NO son peticiones: no generan nada. "Gracias, Helen" solo sirve para rellenar contacto_tal_cual.
3. Una petición de tipo pedido termina en UN solo pedido del ERP. Si el mensaje pide para dos clientes, dos empresas o dos direcciones de entrega, son DOS peticiones de tipo pedido. Si además hay una pregunta, una queja o un comentario, es OTRA petición aparte.
3b. Si te resulta más fácil, deja un solo pedido y rellena en cada línea `destino_tal_cual` con el sitio al que va esa línea ("la nave de Sevilla Este", "la tienda de la calle Sierpes"): el código lo partirá. Si todo va al mismo sitio, `destino_tal_cual` = null.
3c. `tercero_tal_cual` es la empresa o el cliente que pide, tal cual: "soy Jesse, de Relecloud" → "Relecloud"; "de parte de los de Trey Research" → "los de Trey Research". Solo null si el mensaje no nombra ninguna empresa.
4. Copia nombres de artículos, cliente, contacto, unidades, fechas y referencias TAL CUAL aparecen en el mensaje. No inventes códigos, no traduzcas, no completes lo que no está. Si no se dice la cantidad, cantidad = null. Si no se dice la unidad, unidad_tal_cual = null.
4b. Las cantidades casi siempre vienen en letras: "dos sillas" → cantidad 2; "una mesa" → 1; "media docena" → 6; "un palé de escritorios" → cantidad 1 y unidad_tal_cual "palé". Conviértelas a número. Solo "unas cuantas", "varias" o similares son null. Si el cliente se corrige ("cuatro... no, mejor tres"), vale la última.
4c. contacto_tal_cual es quien HABLA o firma ("soy Mariano", "gracias, Helen"), nunca la persona a la que se dirige ("hola Miguel" → Miguel NO es el contacto).
4d. La fecha de entrega se COPIA con las palabras del mensaje ("el jueves", "para el quince", "lo antes posible"). NUNCA calcules ni conviertas una fecha: eso lo hace el código. Si escribes 2026-09-14 donde el mensaje dice "el jueves", es un error.
4e. En campos_dudosos van NOMBRES de campos ("fecha_entrega_tal_cual"), no valores.
5. Una consulta de precio sobre artículos lleva esos artículos en `lineas` con cantidad null.
6. Si el texto viene de una transcripción y hay palabras raras o partes que no cuadran, no las arregles: ponlas en `partes_no_entendidas` o en `campos_dudosos`.
7. `asunto`: una línea corta que sirva en una lista ("Pedido de 2 sillas y 1 mesa para el jueves", "Consulta de precio de escritorios").
8. `confianza`: 1 si estás seguro, baja si dudas. Sé honesto: es mejor una confianza baja que un dato inventado.
9. Responde en español."""


def _usuario(texto: str, fecha_mensaje: datetime, remitente: Optional[str], canal: str) -> str:
    return (
        f"Canal: {canal}\n"
        f"Fecha del mensaje: {fecha_mensaje.strftime('%A %d/%m/%Y')}\n"
        f"Remitente: {remitente or 'desconocido'}\n"
        f"--- MENSAJE ---\n{texto}\n--- FIN ---"
    )


# ----------------------------------------------------------------------------
# Proveedores. Cada uno devuelve el JSON crudo como texto.
# ----------------------------------------------------------------------------


def _ollama(usuario: str, modelo: str) -> str:
    cuerpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}],
        "format": Interpretacion.model_json_schema(),
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 8192},
    }
    try:
        r = requests.post(f"{cfg.llm_url}/api/chat", json=cuerpo, timeout=600)
    except requests.ConnectionError as e:
        raise SystemExit(
            f"No hay Ollama en {cfg.llm_url}. Arráncalo (`ollama serve`) y descarga el modelo (`ollama pull {modelo}`)."
        ) from e
    if r.status_code == 404:
        raise SystemExit(f"Ollama no tiene el modelo {modelo}: `ollama pull {modelo}`")
    r.raise_for_status()
    return r.json()["message"]["content"]


def _gemini(usuario: str, modelo: str) -> str:
    if not cfg.gemini_key:
        raise SystemExit("Falta GEMINI_API_KEY (o GOOGLE_API_KEY) en .env")
    from google import genai
    from google.genai import types

    cliente = genai.Client(api_key=cfg.gemini_key)
    resp = cliente.models.generate_content(
        model=modelo,
        contents=usuario,
        config=types.GenerateContentConfig(
            system_instruction=SISTEMA,
            temperature=0,
            response_mime_type="application/json",
            response_schema=Interpretacion,
        ),
    )
    return resp.text or ""


def _groq(usuario: str, modelo: str) -> str:
    if not cfg.groq_key:
        raise SystemExit("Falta GROQ_API_KEY en .env")
    from openai import BadRequestError, OpenAI

    cliente = OpenAI(api_key=cfg.groq_key, base_url="https://api.groq.com/openai/v1")
    mensajes = [{"role": "system", "content": SISTEMA}, {"role": "user", "content": usuario}]
    try:
        r = cliente.chat.completions.create(
            model=modelo,
            messages=mensajes,
            temperature=0,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "interpretacion", "schema": Interpretacion.model_json_schema()},
            },
        )
    except BadRequestError:
        # El modelo no admite json_schema: JSON libre con el esquema en el prompt, y se valida igual.
        mensajes[1]["content"] += "\n\nDevuelve un JSON que cumpla exactamente este esquema:\n" + json.dumps(
            Interpretacion.model_json_schema(), ensure_ascii=False
        )
        r = cliente.chat.completions.create(
            model=modelo, messages=mensajes, temperature=0, response_format={"type": "json_object"}
        )
    return r.choices[0].message.content or ""


PROVEEDORES = {"ollama": _ollama, "gemini": _gemini, "groq": _groq}


def modelo_por_defecto(backend: str) -> str:
    return {"ollama": cfg.llm_modelo, "gemini": cfg.gemini_modelo, "groq": cfg.groq_modelo}[backend]


def interpretar(
    texto: str,
    fecha_mensaje: datetime,
    remitente: Optional[str],
    canal: str,
    backend: Optional[str] = None,
    modelo: Optional[str] = None,
) -> tuple[Interpretacion, str, str]:
    """Devuelve (interpretación validada, JSON crudo, etiqueta 'backend:modelo')."""
    backend = backend or cfg.llm_backend
    if backend not in PROVEEDORES:
        raise SystemExit(f"Proveedor desconocido: {backend}. Opciones: {', '.join(PROVEEDORES)}")
    modelo = modelo or modelo_por_defecto(backend)
    crudo = PROVEEDORES[backend](_usuario(texto, fecha_mensaje, remitente, canal), modelo)
    try:
        interp = Interpretacion.model_validate_json(crudo)
    except Exception as e:
        # Si no valida, no se inventa nada: el mensaje irá a la persona con lo que haya.
        raise SystemExit(f"La salida de {backend}:{modelo} no cumple el esquema: {e}\n{crudo}") from e
    return interp, crudo, f"{backend}:{modelo}"


def a_json(interp: Interpretacion) -> str:
    return json.dumps(interp.model_dump(mode="json"), ensure_ascii=False, indent=2)
