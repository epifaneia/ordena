"""Salida por consola: el ticket como lo vería la persona, original al lado y dudosos marcados."""
from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .esquema import CampoResuelto, Interpretacion, Mensaje, Ticket

consola = Console(highlight=False)


def _campo(c: CampoResuelto) -> Text:
    t = Text()
    if c.valor:
        t.append(f"{c.valor}", style="bold")
        if c.etiqueta and c.etiqueta != c.valor:
            t.append(f" · {c.etiqueta}")
        if c.puntuacion is not None and c.puntuacion < 100:
            t.append(f" ({c.puntuacion:.0f})", style="dim")
    elif c.tal_cual:
        t.append(f"'{c.tal_cual}'", style="italic")
    else:
        t.append("—", style="dim")
    if c.dudoso:
        t.append("  ⚠ dudoso", style="bold yellow")
        if c.motivo:
            t.append(f": {c.motivo}", style="yellow")
    elif c.motivo:
        t.append(f"  ({c.motivo})", style="dim")
    return t


def mensaje(m: Mensaje) -> None:
    cabecera = f"Mensaje {m.id} · canal {m.canal} · {m.fecha:%d/%m/%Y %H:%M} · remitente {m.remitente or 'desconocido'}"
    cuerpo = Text()
    if m.transcripcion:
        cuerpo.append(f"Transcripción ({m.transcripcion.modelo}, {m.transcripcion.duracion:.0f} s):\n", style="dim")
        for s in m.transcripcion.segmentos:
            cuerpo.append(f"[{s.inicio:5.1f}] ", style="dim")
            cuerpo.append(s.texto + "\n", style="yellow" if s.dudoso else "")
    else:
        cuerpo.append(m.texto)
    consola.print(Panel(cuerpo, title=cabecera, box=box.ROUNDED))


def interpretacion(i: Interpretacion) -> None:
    consola.print(
        f"[dim]Interpretación: {len(i.peticiones)} petición(es), confianza global {i.confianza_global:.2f}"
        + (f", partes no entendidas: {i.partes_no_entendidas}" if i.partes_no_entendidas else "")
        + "[/dim]"
    )


def ticket(t: Ticket) -> None:
    titulo = f"Ticket {t.id} · {t.tipo.value.upper()} · " + (
        "[bold red]exige validación[/bold red]" if t.exige_validacion else "[dim]informativo[/dim]"
    )
    if t.incompleto:
        titulo += f" · [bold magenta]INCOMPLETO[/bold magenta] (falta: {', '.join(t.incompleto)})"
    if t.erp_numero:
        titulo += f" · [bold green]ERP {t.erp_numero}[/bold green]"

    cuerpo = Table.grid(padding=(0, 1))
    cuerpo.add_column(style="dim", justify="right")
    cuerpo.add_column()
    cuerpo.add_row("asunto", Text(t.asunto, style="bold"))
    cuerpo.add_row("resumen", t.resumen)
    cuerpo.add_row("cliente", _campo(t.cliente))
    if t.contacto:
        cuerpo.add_row("contacto", t.contacto)
    cuerpo.add_row("entrega", _campo(t.direccion_entrega))
    cuerpo.add_row("fecha", _campo(t.fecha_entrega))
    if t.referencia_cliente:
        cuerpo.add_row("ref. cliente", t.referencia_cliente)
    if t.se_refiere_a.tal_cual:
        cuerpo.add_row("se refiere a", _campo(t.se_refiere_a))
    if t.observaciones:
        cuerpo.add_row("observaciones", t.observaciones)
    cuerpo.add_row("confianza", f"{t.confianza:.2f}")
    if t.hermanos:
        cuerpo.add_row("hermanos", ", ".join(t.hermanos))

    consola.print(Panel(cuerpo, title=titulo, box=box.ROUNDED))

    if t.lineas:
        tabla = Table(box=box.SIMPLE_HEAD, show_edge=False)
        tabla.add_column("#", style="dim")
        tabla.add_column("tal cual", style="italic")
        tabla.add_column("cantidad", justify="right")
        tabla.add_column("unidad")
        tabla.add_column("artículo resuelto")
        tabla.add_column("tarifa", justify="right")
        for n, l in enumerate(t.lineas, 1):
            cant = f"{l.cantidad:g}" if l.cantidad is not None else Text("?", style="bold magenta")
            tabla.add_row(
                str(n), l.original.descripcion_tal_cual, cant, _campo(l.unidad), _campo(l.articulo),
                f"{l.precio_tarifa:.2f}" if l.precio_tarifa is not None else "—",
            )
        consola.print(tabla)

    if t.dudosos:
        consola.print("  [yellow]⚠ dudosos:[/yellow]")
        for d in t.dudosos:
            consola.print(f"    · {d}")
    consola.print()


def aviso(texto: str) -> None:
    consola.print(f"[bold cyan]»[/bold cyan] {texto}")
