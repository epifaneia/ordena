"""Pruebas sin red y sin modelo: interpretaciones escritas a mano contra los maestros de demostración.

    python tests/test_tickets.py

Sale con código distinto de cero si algo falla.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ordena_poc.esquema import Interpretacion, LineaPedida, Mensaje, Peticion, TipoPeticion  # noqa: E402
from ordena_poc.maestros import Maestros  # noqa: E402
from ordena_poc.resolver import deducir_cantidad, normalizar, resolver_cliente, resolver_fecha  # noqa: E402
from ordena_poc.tickets import NO_LITERAL, construir  # noqa: E402

# Siempre los de demostración (CRONUS), aunque haya unos descargados de Business Central.
MAESTROS = Maestros.model_validate_json((RAIZ / "data" / "maestros_demo.json").read_text(encoding="utf-8"))
FECHA = datetime(2026, 10, 26, 10, 0)  # lunes

fallos: list[str] = []


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    print(f"{'ok   ' if condicion else 'FALLA'} {nombre}" + (f" → {detalle}" if detalle and not condicion else ""))
    if not condicion:
        fallos.append(nombre)


def mensaje(texto: str, asunto: str | None = "pedido", remitente: str | None = None) -> Mensaje:
    return Mensaje(id="prueba", canal="correo", fecha=FECHA, remitente=remitente, asunto=asunto, texto=texto, hash="0")


def linea(descripcion: str, cantidad: float | None) -> LineaPedida:
    return LineaPedida(
        descripcion_tal_cual=descripcion, cantidad=cantidad, unidad_tal_cual=None, precio_mencionado=None,
        referencia_mencionada=None, destino_tal_cual=None, duda=None,
    )


def pedido(tercero: str | None, direccion: str | None, lineas: list[LineaPedida]) -> Interpretacion:
    p = Peticion(
        tipo=TipoPeticion.pedido, asunto="pedido", resumen="pedido", tercero_tal_cual=tercero,
        contacto_tal_cual=None, direccion_entrega_tal_cual=direccion, fecha_entrega_tal_cual="lo antes que puedas",
        referencia_cliente=None, se_refiere_a_tal_cual=None, lineas=lineas, observaciones=None,
        campos_dudosos=[], confianza=0.9,
    )
    return Interpretacion(peticiones=[p], partes_no_entendidas=[], confianza_global=0.9)


def no_literales(t) -> list[str]:
    return [d for d in t.dudosos if NO_LITERAL in d]


TEXTO = "Mira, soy Jesse, de Relecloud. Me mandas tres lámparas de Amsterdam a la nave de Sevilla Este. Lo antes que puedas."

# --- Literalidad de lo que copia el modelo -----------------------------------

# El caso real con qwen2.5:7b: el mensaje dice "lámparas" y el modelo devuelve "lámpera".
[t] = construir(mensaje(TEXTO), pedido("Relecloud", "la nave de Sevilla Este", [linea("lámpera de Amsterdam", 3)]), MAESTROS)
check("lámpera: la línea queda dudosa", t.lineas[0].dudoso)
check("lámpera: el artículo lleva el motivo", (t.lineas[0].articulo.motivo or "").startswith(NO_LITERAL), str(t.lineas[0].articulo.motivo))
check("lámpera: aviso visible en el ticket", any("línea 1" in d and "lámpera de Amsterdam" in d for d in no_literales(t)), str(t.dudosos))
check("lámpera: no se corrige en silencio", t.lineas[0].original.descripcion_tal_cual == "lámpera de Amsterdam")
check("lámpera: cliente y dirección literales no se marcan", len(no_literales(t)) == 1, str(no_literales(t)))

# Copiado literal: ningún aviso de literalidad.
[t] = construir(mensaje(TEXTO), pedido("Relecloud", "la nave de Sevilla Este", [linea("lámparas de Amsterdam", 3)]), MAESTROS)
check("literal: sin avisos de literalidad", not no_literales(t), str(no_literales(t)))
check("literal: el artículo no lleva el motivo", NO_LITERAL not in (t.lineas[0].articulo.motivo or ""))

# Solo cambian mayúsculas, tildes, signos y espacios: es la misma copia.
[t] = construir(
    mensaje(TEXTO),
    pedido("  RELECLOUD ", "la nave de  sevilla  este", [linea("Lamparas   de amsterdam", 3)]),
    MAESTROS,
)
check("mayúsculas/tildes/espacios: sin avisos de literalidad", not no_literales(t), str(no_literales(t)))

# Cliente y dirección que el mensaje no dice así.
[t] = construir(mensaje(TEXTO), pedido("Relecloud S.A.", "nave de Sevilla Oeste", [linea("lámparas de Amsterdam", 3)]), MAESTROS)
check("cliente no literal: marcado dudoso", t.cliente.dudoso and (t.cliente.motivo or "").startswith(NO_LITERAL), str(t.cliente.motivo))
check("cliente no literal: aviso visible", any(d.startswith("cliente:") for d in no_literales(t)), str(t.dudosos))
check("dirección no literal: marcada dudosa", t.direccion_entrega.dudoso and NO_LITERAL in (t.direccion_entrega.motivo or ""))
check("dirección no literal: aviso visible", any(d.startswith("dirección:") for d in no_literales(t)), str(t.dudosos))

# El asunto también es el mensaje.
[t] = construir(mensaje("Lo de siempre, gracias.", asunto="Pedido de Relecloud"), pedido("Relecloud", None, []), MAESTROS)
check("asunto: lo copiado del asunto cuenta como literal", not no_literales(t), str(no_literales(t)))

# --- resolver.py: lógica pura ------------------------------------------------

check("normalizar: tildes, mayúsculas, signos y espacios", normalizar("  Lámparas,  de ÁMSTERDAM! ") == "lamparas de amsterdam")

c = resolver_cliente(None, "JESSE.HOMER@contoso.com", MAESTROS)
check("cliente por remitente conocido", c.valor == "50000" and not c.dudoso, f"{c.valor} {c.motivo}")

c = resolver_cliente("Relecloud", "jesse.homer@contoso.com", MAESTROS)
check("remitente y mensaje dicen el mismo cliente: seguro", c.valor == "50000" and not c.dudoso, f"{c.valor} {c.motivo}")

# Caso de la revisión del 30 oct: Jesse (Relecloud) escribe «de parte de los de Trey Research».
c = resolver_cliente("los de Trey Research", "jesse.homer@contoso.com", MAESTROS)
check("remitente de un cliente y mensaje de otro: no se elige, se marca",
      c.valor is None and c.dudoso and "20000" in (c.motivo or "") and len(c.candidatos) == 2, f"{c.valor} {c.motivo}")

f = resolver_fecha("el jueves", FECHA)
check("fecha relativa: el jueves desde el lunes 26/10/2026", f.valor == "2026-10-29" and f.dudoso, f"{f.valor} {f.motivo}")

f = resolver_fecha("2026-11-02", FECHA, "para el lunes que viene")
check("fecha ISO que no está en el mensaje: dudosa", f.dudoso and "calculada por el modelo" in (f.motivo or ""), str(f.motivo))

check("cantidad en letras: tres lámparas", deducir_cantidad(TEXTO, "lámparas de Amsterdam") == (3.0, "tres"))

print()
if fallos:
    print(f"{len(fallos)} fallo(s): {', '.join(fallos)}")
    sys.exit(1)
print("Todo bien.")
