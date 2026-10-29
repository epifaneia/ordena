"""De la interpretación resuelta a tickets.

Reglas: un ticket termina en un solo sitio. Una petición del
modelo es un ticket. Si el modelo no encuentra ninguna, sigue habiendo un
ticket: siempre ticket. Los tickets del mismo mensaje son hermanos.
"""
from __future__ import annotations

import re
from typing import Optional

from .config import cfg
from .esquema import (
    EXIGEN_VALIDACION,
    CampoResuelto,
    Interpretacion,
    LineaResuelta,
    Mensaje,
    Origen,
    Peticion,
    Ticket,
    TipoPeticion,
)
from .maestros import Maestros
from .resolver import (
    articulo_por_numero,
    cliente_por_numero,
    comprobar_precio,
    deducir_cantidad,
    deducir_cliente,
    normalizar,
    resolver_articulo,
    resolver_cliente,
    resolver_direccion,
    resolver_fecha,
    resolver_unidad,
)


def _numero_en_texto(valor: float, texto: str) -> bool:
    """Un número dicho por el modelo tiene que estar en el mensaje, en cifra o en letras."""
    from .resolver import NUMEROS

    ntexto = normalizar(texto)
    formas = {f"{valor:g}", f"{valor:.2f}".replace(".", ","), f"{valor:.2f}"}
    if valor == int(valor):
        formas |= {str(int(valor))} | {palabra for palabra, n in NUMEROS.items() if n == int(valor)}
    return any(re.search(rf"(?<![0-9a-z]){re.escape(f)}(?![0-9a-z])", ntexto) for f in formas)


NO_LITERAL = "el modelo no copió literal: no está en el mensaje"


def _copiado_literal(tal_cual: Optional[str], texto: str) -> bool:
    """Lo que el modelo dice copiar tiene que estar en el mensaje. Se perdonan mayúsculas,
    tildes, signos y espacios (normalizar); una letra cambiada, no: "lámpera" no es "lámparas"."""
    if not tal_cual or not tal_cual.strip():
        return True
    ntal = normalizar(tal_cual)
    return not ntal or f" {ntal}" in f" {normalizar(texto)}"


def _marcar_no_literal(campo: CampoResuelto) -> None:
    """No se corrige: se marca dudoso y se dice por qué, conservando el motivo que hubiera."""
    previo = f"; {campo.motivo}" if campo.dudoso and campo.motivo else ""
    campo.dudoso = True
    campo.motivo = NO_LITERAL + previo


def _destino(l, p: Peticion) -> str:
    return (l.destino_tal_cual or p.direccion_entrega_tal_cual or "").strip()


def _partir_por_destino(p: Peticion) -> list[tuple[Peticion, Optional[str]]]:
    """Un ticket de pedido es un pedido del ERP: una dirección de entrega.
    Si las líneas van a sitios distintos, el código parte la petición. Devuelve (petición, motivo)."""
    if p.tipo not in EXIGEN_VALIDACION or len(p.lineas) < 2:
        return [(p, None)]
    destinos: list[str] = []
    for l in p.lineas:
        d = _destino(l, p)
        if d not in destinos:
            destinos.append(d)
    if len(destinos) < 2:
        return [(p, None)]
    partes = []
    for d in destinos:
        lineas = [l for l in p.lineas if _destino(l, p) == d]
        parte = p.model_copy(
            update={
                "lineas": lineas,
                "direccion_entrega_tal_cual": d or p.direccion_entrega_tal_cual,
                "asunto": f"{p.asunto} · {d}" if d else p.asunto,
            }
        )
        partes.append((parte, f"partido por el código: el mensaje pide a varios sitios ({', '.join(x or 'sin destino' for x in destinos)})"))
    return partes


def _lineas(p: Peticion, m: Maestros, texto_mensaje: str, texto_literal: Optional[str] = None) -> tuple[list[LineaResuelta], list[str]]:
    lineas: list[LineaResuelta] = []
    dudosos: list[str] = []
    for n, l in enumerate(p.lineas, 1):
        art = resolver_articulo(l, m)
        if not _copiado_literal(l.descripcion_tal_cual, texto_literal or texto_mensaje):
            # "lámpera de Amsterdam" cuando el mensaje dice "lámparas": el artículo puede salir bien, pero no nos fiamos.
            _marcar_no_literal(art)
        articulo = articulo_por_numero(art.valor, m)
        unidad = resolver_unidad(l.unidad_tal_cual, articulo)
        aviso_precio = comprobar_precio(l.precio_mencionado, articulo)
        if l.precio_mencionado is not None and not _numero_en_texto(l.precio_mencionado, texto_mensaje):
            # "a mitad de precio" no es un precio: el modelo lo ha convertido en número. No nos fiamos.
            aviso_precio = f"precio {l.precio_mencionado:g} no aparece en el mensaje; el modelo lo ha calculado"
        cantidad = l.cantidad
        deducida = None
        if cantidad is None and p.tipo in EXIGEN_VALIDACION:
            # El modelo copia; el código garantiza. "dos sillas" tiene que valer 2 aunque el modelo lo pierda.
            cantidad, deducida = deducir_cantidad(texto_mensaje, l.descripcion_tal_cual)
        dudoso = art.dudoso or unidad.dudoso or bool(l.duda) or bool(aviso_precio) or bool(deducida)
        if art.dudoso:
            dudosos.append(f"línea {n} artículo: {art.motivo} ('{l.descripcion_tal_cual}')")
        if unidad.dudoso:
            dudosos.append(f"línea {n} unidad: {unidad.motivo}")
        if deducida:
            dudosos.append(f"línea {n} cantidad: deducida del texto ('{deducida}'), el modelo no la dio")
        if l.duda:
            dudosos.append(f"línea {n}: {l.duda}")
        if aviso_precio:
            dudosos.append(f"línea {n}: {aviso_precio}")
        lineas.append(
            LineaResuelta(
                original=l, articulo=art, unidad=unidad, cantidad=cantidad,
                precio_tarifa=articulo.precio if articulo else None, dudoso=dudoso,
            )
        )
    return lineas, dudosos


def _incompleto(p: Peticion, cliente: CampoResuelto, fecha: CampoResuelto, lineas: list[LineaResuelta]) -> list[str]:
    if p.tipo != TipoPeticion.pedido:
        return []
    faltan: list[str] = []
    obligatorios = set(cfg.campos_obligatorios)
    if "cliente" in obligatorios and not cliente.valor:
        faltan.append("cliente")
    if "lineas" in obligatorios and not lineas:
        faltan.append("líneas")
    if "cantidad" in obligatorios and any(l.cantidad is None for l in lineas):
        faltan.append("cantidad en alguna línea")
    if "fecha_entrega" in obligatorios and not fecha.valor and not fecha.tal_cual:
        # "lo antes que puedas" es una fecha dicha aunque no se pueda calcular: dudosa, no ausente.
        faltan.append("fecha de entrega")
    if "direccion_entrega" in obligatorios and not p.direccion_entrega_tal_cual:
        faltan.append("dirección de entrega")
    return faltan


def _ticket(mensaje: Mensaje, p: Peticion, n: int, m: Maestros, motivo_particion: Optional[str] = None) -> Ticket:
    cliente = resolver_cliente(p.tercero_tal_cual, mensaje.remitente, m)
    if not cliente.valor and not p.tercero_tal_cual:
        cliente = deducir_cliente(mensaje.texto, m)
    ficha = cliente_por_numero(cliente.valor, m)
    direccion = resolver_direccion(p.direccion_entrega_tal_cual, ficha)
    texto_literal = " ".join(x for x in (mensaje.asunto, mensaje.texto) if x)
    if not _copiado_literal(p.tercero_tal_cual, texto_literal):
        _marcar_no_literal(cliente)
    if not _copiado_literal(p.direccion_entrega_tal_cual, texto_literal):
        _marcar_no_literal(direccion)
    fecha_tal_cual = p.fecha_entrega_tal_cual
    if fecha_tal_cual and p.direccion_entrega_tal_cual and normalizar(fecha_tal_cual).replace("para ", "") == normalizar(p.direccion_entrega_tal_cual).replace("para ", ""):
        # "para el almacén de Sevilla Este" es un destino, no una fecha. Los modelos pequeños lo confunden.
        fecha_tal_cual = None
    fecha = resolver_fecha(fecha_tal_cual, mensaje.fecha, mensaje.texto)
    if p.fecha_entrega_tal_cual and not fecha_tal_cual:
        fecha.motivo = "el modelo puso el destino como fecha; no hay fecha en el mensaje"
    lineas, dudosos_lineas = _lineas(p, m, mensaje.texto, texto_literal)

    dudosos: list[str] = []
    if cliente.dudoso:
        dudosos.append(f"cliente: {cliente.motivo}")
    if direccion.dudoso:
        dudosos.append(f"dirección: {direccion.motivo}")
    if fecha.dudoso:
        dudosos.append(f"fecha: {fecha.motivo}")
    dudosos += dudosos_lineas
    dudosos += [f"el modelo duda de: {c}" for c in p.campos_dudosos]
    if motivo_particion:
        dudosos.append(motivo_particion)

    se_refiere_a = CampoResuelto(
        tal_cual=p.se_refiere_a_tal_cual,
        dudoso=bool(p.se_refiere_a_tal_cual),
        motivo="referencia a algo anterior; en la PoC no se busca en el histórico" if p.se_refiere_a_tal_cual else None,
    )
    if se_refiere_a.dudoso:
        dudosos.append("se refiere a un pedido anterior que hay que localizar")

    return Ticket(
        id=f"{mensaje.id}-{n}",
        tipo=p.tipo,
        exige_validacion=p.tipo in EXIGEN_VALIDACION,
        asunto=p.asunto,
        resumen=p.resumen,
        cliente=cliente,
        contacto=p.contacto_tal_cual,
        direccion_entrega=direccion,
        fecha_entrega=fecha,
        referencia_cliente=p.referencia_cliente,
        se_refiere_a=se_refiere_a,
        lineas=lineas,
        observaciones=p.observaciones,
        incompleto=_incompleto(p, cliente, fecha, lineas),
        dudosos=dudosos,
        confianza=p.confianza,
        origen=Origen(mensaje_id=mensaje.id, canal=mensaje.canal),
    )


def construir(mensaje: Mensaje, interp: Interpretacion, m: Maestros) -> list[Ticket]:
    partes = [pm for p in interp.peticiones for pm in _partir_por_destino(p)]
    tickets = [_ticket(mensaje, p, n, m, motivo) for n, (p, motivo) in enumerate(partes, 1)]
    if not tickets:
        # Siempre ticket: un mensaje sin petición reconocida no desaparece.
        resumen = " · ".join(interp.partes_no_entendidas) or mensaje.texto[:300]
        tickets.append(
            Ticket(
                id=f"{mensaje.id}-1",
                tipo=TipoPeticion.comentario,
                exige_validacion=False,
                asunto="Mensaje sin petición reconocida",
                resumen=resumen,
                cliente=resolver_cliente(None, mensaje.remitente, m),
                direccion_entrega=CampoResuelto(dudoso=False),
                fecha_entrega=CampoResuelto(dudoso=False),
                se_refiere_a=CampoResuelto(dudoso=False),
                confianza=interp.confianza_global,
                origen=Origen(mensaje_id=mensaje.id, canal=mensaje.canal),
                dudosos=["el modelo no ha reconocido ninguna petición: revisar el original"],
            )
        )
    ids = [t.id for t in tickets]
    for t in tickets:
        t.hermanos = [i for i in ids if i != t.id]
    _heredar_entre_hermanos(tickets)
    return tickets


def _heredar_entre_hermanos(tickets: list[Ticket]) -> None:
    """Si una petición del mismo mensaje no nombra al cliente o al contacto y otra sí,
    se hereda como dudoso: un mensaje lo manda una sola persona de una sola empresa."""
    con_cliente = next((t for t in tickets if t.cliente.valor or t.cliente.tal_cual), None)
    con_contacto = next((t for t in tickets if t.contacto), None)
    for t in tickets:
        if con_cliente and t is not con_cliente and not t.cliente.valor and not t.cliente.tal_cual:
            t.cliente = con_cliente.cliente.model_copy(
                update={"dudoso": True, "motivo": f"heredado del ticket {con_cliente.id} del mismo mensaje"}
            )
            t.dudosos = [d for d in t.dudosos if not d.startswith("cliente:")] + [f"cliente: {t.cliente.motivo}"]
        if con_contacto and t is not con_contacto and not t.contacto:
            t.contacto = con_contacto.contacto
