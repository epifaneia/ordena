"""Resolución contra maestros: de "lo de siempre" a código, unidad y fecha.

Determinista. Cuando no puede decidir, marca dudoso y deja candidatos; nunca
elige por el humano.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Optional

from rapidfuzz import fuzz, process

from .esquema import CampoResuelto, LineaPedida
from .maestros import Articulo, Cliente, Maestros

# Umbrales. Se ajustan en la validación con sus documentos, no aquí.
SEGURO_CLIENTE = 88
SEGURO_ARTICULO = 85
CORTE = 55
MARGEN = 8  # si el segundo candidato está a menos de esto del primero, es ambiguo

UNIDADES = {
    "ud": "UDS", "uds": "UDS", "unidad": "UDS", "unidades": "UDS", "pieza": "UDS", "piezas": "UDS", "pcs": "UDS",
    "caja": "CAJA", "cajas": "CAJA",
    "pale": "PALÉ", "pales": "PALÉ", "palet": "PALÉ", "palets": "PALÉ", "palé": "PALÉ", "palés": "PALÉ", "pallet": "PALÉ",
    "kg": "KG", "kilo": "KG", "kilos": "KG",
    "saco": "SACO", "sacos": "SACO",
    "litro": "L", "litros": "L", "l": "L",
    "bote": "BOTE", "botes": "BOTE",
}

PALABRAS_VACIAS = {"de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "esas", "esos", "esa", "ese", "para", "y", "con"}

# Cantidades en letras: "dos sillas", "media docena", "un palé".
NUMEROS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20, "veintiuno": 21,
    "veintiuna": 21, "veintidos": 22, "veintitres": 23, "veinticuatro": 24, "veinticinco": 25,
    "veintiseis": 26, "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "treinta": 30,
    "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "cien": 100, "medio": 0.5, "media": 0.5,
}
DIAS_SEMANA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
RELLENO_FECHA = {"para", "el", "la", "los", "las", "dia", "de", "este", "esta", "a", "sobre", "hacia"}


def normalizar(s: Optional[str]) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9ñ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _tokens(s: str) -> list[str]:
    salida = []
    for t in normalizar(s).split():
        if t in PALABRAS_VACIAS:
            continue
        if len(t) > 3 and t.endswith("s"):
            t = t[:-1]  # singular aproximado: sillas → silla, giratorias → giratoria
        salida.append(t)
    return salida


def _clave(s: str) -> str:
    return " ".join(_tokens(s))


def _elegir(tal_cual: str, opciones: list[tuple[str, str, str]], scorer, seguro: int) -> CampoResuelto:
    """opciones: (clave normalizada, código, etiqueta). Devuelve el campo con dudoso decidido."""
    claves = [o[0] for o in opciones]
    resultados = process.extract(_clave(tal_cual), claves, scorer=scorer, limit=3, score_cutoff=CORTE)
    if not resultados:
        return CampoResuelto(tal_cual=tal_cual, dudoso=True, motivo="sin parecido suficiente en los maestros")
    mejor = resultados[0]
    segundo = resultados[1][1] if len(resultados) > 1 else 0
    _, puntuacion, indice = mejor
    codigo, etiqueta = opciones[indice][1], opciones[indice][2]
    candidatos = [f"{opciones[r[2]][1]} · {opciones[r[2]][2]} ({r[1]:.0f})" for r in resultados]
    ambiguo = (puntuacion - segundo) < MARGEN and len(resultados) > 1
    dudoso = puntuacion < seguro or ambiguo
    motivo = None
    if ambiguo:
        motivo = "varios candidatos parecidos"
    elif puntuacion < seguro:
        motivo = "parecido bajo"
    return CampoResuelto(
        tal_cual=tal_cual, valor=codigo, etiqueta=etiqueta, puntuacion=round(float(puntuacion), 1),
        dudoso=dudoso, motivo=motivo, candidatos=candidatos,
    )


def resolver_cliente(tal_cual: Optional[str], remitente: Optional[str], m: Maestros) -> CampoResuelto:
    if remitente:
        for c in m.clientes:
            if c.email and c.email.lower() == remitente.lower():
                return CampoResuelto(
                    tal_cual=tal_cual, valor=c.numero, etiqueta=c.nombre, puntuacion=100.0,
                    dudoso=False, motivo="remitente conocido en la ficha del cliente",
                )
    if not tal_cual:
        return CampoResuelto(dudoso=True, motivo="el mensaje no nombra al cliente y el remitente no está en ninguna ficha")
    opciones = [(_clave(c.nombre), c.numero, c.nombre) for c in m.clientes]
    return _elegir(tal_cual, opciones, fuzz.WRatio, SEGURO_CLIENTE)


def deducir_cliente(texto: str, m: Maestros) -> CampoResuelto:
    """Si el modelo no extrajo el cliente, buscar nombres de clientes dentro del mensaje.
    Siempre dudoso: lo propone el código, lo confirma la persona."""
    ntexto = f" {normalizar(texto)} "
    encontrados = [c for c in m.clientes if c.nombre and f" {normalizar(c.nombre)} " in ntexto]
    if len(encontrados) == 1:
        c = encontrados[0]
        return CampoResuelto(
            valor=c.numero, etiqueta=c.nombre, puntuacion=100.0, dudoso=True,
            motivo="nombrado en el mensaje; el modelo no lo extrajo, confirmar",
        )
    if len(encontrados) > 1:
        return CampoResuelto(
            dudoso=True, motivo="el mensaje nombra a varios clientes",
            candidatos=[f"{c.numero} · {c.nombre}" for c in encontrados],
        )
    return CampoResuelto(dudoso=True, motivo="el mensaje no nombra al cliente y el remitente no está en ninguna ficha")


def cliente_por_numero(numero: Optional[str], m: Maestros) -> Optional[Cliente]:
    return next((c for c in m.clientes if c.numero == numero), None)


def articulo_por_numero(numero: Optional[str], m: Maestros) -> Optional[Articulo]:
    return next((a for a in m.articulos if a.numero == numero), None)


def resolver_articulo(linea: LineaPedida, m: Maestros) -> CampoResuelto:
    if linea.referencia_mencionada:
        for a in m.articulos:
            if a.numero.lower() == linea.referencia_mencionada.strip().lower():
                return CampoResuelto(
                    tal_cual=linea.descripcion_tal_cual, valor=a.numero, etiqueta=a.nombre,
                    puntuacion=100.0, dudoso=False, motivo="referencia citada en el mensaje",
                )
    opciones = [(_clave(a.nombre), a.numero, a.nombre) for a in m.articulos if not a.bloqueado]
    return _elegir(linea.descripcion_tal_cual, opciones, fuzz.token_set_ratio, SEGURO_ARTICULO)


def resolver_unidad(unidad_tal_cual: Optional[str], articulo: Optional[Articulo]) -> CampoResuelto:
    if articulo is None:
        return CampoResuelto(tal_cual=unidad_tal_cual, dudoso=True, motivo="sin artículo no hay unidad")
    if not unidad_tal_cual:
        return CampoResuelto(
            valor=articulo.unidad_base, etiqueta=articulo.unidad_base, dudoso=False, motivo="unidad base",
        )
    codigo = UNIDADES.get(normalizar(unidad_tal_cual))
    if codigo is None:
        return CampoResuelto(tal_cual=unidad_tal_cual, dudoso=True, motivo="unidad no reconocida")
    permitidas = {articulo.unidad_base, *articulo.unidades_alternativas}
    if codigo in permitidas:
        return CampoResuelto(tal_cual=unidad_tal_cual, valor=codigo, etiqueta=codigo, dudoso=False)
    return CampoResuelto(
        tal_cual=unidad_tal_cual, valor=codigo, etiqueta=codigo, dudoso=True,
        motivo=f"la unidad {codigo} no existe para el artículo (tiene {', '.join(sorted(p for p in permitidas if p))})",
    )


def _limpiar_fecha(tal_cual: str) -> str:
    """'para el jueves' → 'jueves'; 'el quince' → '15'; 'el día 3 de octubre' → '3 de octubre'."""
    tokens = normalizar(tal_cual).split()
    while tokens and tokens[0] in RELLENO_FECHA:
        tokens.pop(0)
    salida = []
    for t in tokens:
        n = NUMEROS.get(t)
        salida.append(str(int(n)) if n is not None and n == int(n) and n <= 31 else t)
    return " ".join(salida)


def _proximo_dia_del_mes(dia: int, base: datetime) -> Optional[datetime]:
    from calendar import monthrange

    anio, mes = base.year, base.month
    for _ in range(3):
        if dia <= monthrange(anio, mes)[1]:
            candidata = base.replace(year=anio, month=mes, day=dia, hour=0, minute=0, second=0, microsecond=0)
            if candidata.date() >= base.date():
                return candidata
        mes += 1
        if mes > 12:
            mes, anio = 1, anio + 1
    return None


def resolver_fecha(tal_cual: Optional[str], fecha_mensaje: datetime, texto_mensaje: str = "") -> CampoResuelto:
    if not tal_cual:
        return CampoResuelto(dudoso=False, motivo="no se indica fecha de entrega")
    try:
        import dateparser
    except ImportError:  # pragma: no cover
        return CampoResuelto(tal_cual=tal_cual, dudoso=True, motivo="falta dateparser")

    # Guardarraíl: el modelo tiene que copiar la fecha con las palabras del mensaje.
    # Si devuelve una fecha calculada (2026-09-14) que el mensaje no contiene, no nos
    # fiamos: los modelos grandes "ayudan" calculando, y se equivocan de día.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", tal_cual.strip()) and tal_cual.strip() not in texto_mensaje:
        try:
            fecha_calc = datetime.fromisoformat(tal_cual.strip())
        except ValueError:
            fecha_calc = None
        return CampoResuelto(
            tal_cual=tal_cual, valor=fecha_calc.date().isoformat() if fecha_calc else None,
            etiqueta=f"{DIAS_SEMANA[fecha_calc.weekday()]} {fecha_calc:%d/%m/%Y}" if fecha_calc else None,
            dudoso=True, motivo="fecha calculada por el modelo, no copiada del mensaje; comprobar contra el original",
        )

    limpio = _limpiar_fecha(tal_cual)
    fecha: Optional[datetime] = None
    if limpio.isdigit():  # "el quince" → el próximo día 15
        fecha = _proximo_dia_del_mes(int(limpio), fecha_mensaje)
    ajustes = {
        "RELATIVE_BASE": fecha_mensaje,
        "PREFER_DATES_FROM": "future",
        "PREFER_DAY_OF_MONTH": "first",
        "RETURN_AS_TIMEZONE_AWARE": False,
    }
    # "ayer por la tarde", "el jueves a primera hora": se prueba entero y, si no, recortando por el final.
    palabras = limpio.split()
    intentos = [limpio, tal_cual] + [" ".join(palabras[:n]) for n in range(len(palabras) - 1, 0, -1)]
    for intento in intentos:
        if fecha is not None:
            break
        fecha = dateparser.parse(intento, languages=["es"], settings=ajustes)
    if fecha is None:
        return CampoResuelto(tal_cual=tal_cual, dudoso=True, motivo="no se ha podido interpretar la fecha")
    relativa = not re.search(r"\d", limpio) or limpio.isdigit()
    etiqueta = f"{DIAS_SEMANA[fecha.weekday()]} {fecha:%d/%m/%Y}"
    if fecha.date() < fecha_mensaje.date():
        # "para ayer" y similares: una entrega no puede ser anterior al mensaje. Se enseña, no se usa.
        return CampoResuelto(
            tal_cual=tal_cual, valor=None, etiqueta=etiqueta, dudoso=True,
            motivo=f"fecha anterior al mensaje ({etiqueta}); el cliente pide urgencia, no una fecha",
        )
    return CampoResuelto(
        tal_cual=tal_cual, valor=fecha.date().isoformat(), etiqueta=etiqueta,
        dudoso=relativa, motivo="fecha relativa; confirmar" if relativa else None,
    )


def deducir_cantidad(texto: str, descripcion: str) -> tuple[Optional[float], Optional[str]]:
    """Si el modelo no dio cantidad, buscar en el mensaje un número (en cifra o en letras)
    justo antes de las primeras palabras de la descripción. Devuelve (cantidad, palabra encontrada)."""
    toks_desc = _tokens(descripcion)
    if not toks_desc:
        return None, None
    toks_texto = normalizar(texto).split()
    primera = toks_desc[0]
    for i, t in enumerate(toks_texto):
        t_sing = t[:-1] if len(t) > 3 and t.endswith("s") else t
        if t_sing != primera:
            continue
        # hasta tres palabras antes: "dos sillas", "un palé de", "media docena de"
        for j in range(i - 1, max(-1, i - 4), -1):
            palabra = toks_texto[j]
            if palabra.isdigit() or re.fullmatch(r"\d+[.,]\d+", palabra):
                return float(palabra.replace(",", ".")), palabra
            if palabra in NUMEROS:
                cantidad = float(NUMEROS[palabra])
                if palabra in ("media", "medio") and j + 1 < len(toks_texto) and toks_texto[j + 1] == "docena":
                    cantidad = 6.0
                return cantidad, palabra
            if palabra in PALABRAS_VACIAS or palabra in {"docena", "par"}:
                continue
            break
    return None, None


def resolver_direccion(tal_cual: Optional[str], cliente: Optional[Cliente]) -> CampoResuelto:
    if not tal_cual:
        if cliente and len(cliente.direcciones) > 1:
            return CampoResuelto(dudoso=True, motivo="el cliente tiene varias direcciones y el mensaje no dice cuál")
        return CampoResuelto(dudoso=False, motivo="dirección por defecto del cliente")
    if not cliente or not cliente.direcciones:
        return CampoResuelto(tal_cual=tal_cual, dudoso=True, motivo="dirección nombrada pero sin direcciones en la ficha")
    opciones = [(_clave(d), str(i), d) for i, d in enumerate(cliente.direcciones)]
    return _elegir(tal_cual, opciones, fuzz.token_set_ratio, SEGURO_ARTICULO)


def comprobar_precio(precio_mencionado: Optional[float], articulo: Optional[Articulo]) -> Optional[str]:
    """El precio no se sobrescribe: si difiere de la tarifa, se marca."""
    if precio_mencionado is None or articulo is None or articulo.precio is None:
        return None
    if abs(precio_mencionado - articulo.precio) > max(0.01, 0.01 * articulo.precio):
        return f"precio del mensaje {precio_mencionado} distinto de la tarifa {articulo.precio}"
    return None
