"""Ordena · PoC · línea de comandos.

    python -m ordena_poc.main procesar ejemplos/pedido_ejemplo.txt --interpretacion ejemplos/interpretacion_ejemplo.json
    python -m ordena_poc.main procesar audios/pedido1.m4a
    python -m ordena_poc.main procesar audios/pedido1.m4a --llm gemini --stt groq
    python -m ordena_poc.main procesar audios/pedido1.m4a --crear
    python -m ordena_poc.main comparar audios/pedido1.m4a --stt local,groq --llm ollama:qwen2.5:7b,ollama:qwen2.5:14b,gemini,groq
    python -m ordena_poc.main maestros
    python -m ordena_poc.main probar-bc
    python -m ordena_poc.main transcribir audios/pedido1.m4a [--stt groq]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import maestros as M
from . import mostrar
from .config import cfg
from .esquema import Interpretacion, Mensaje, Ticket, TipoPeticion
from .tickets import construir
from .transcribir import es_audio, transcribir


def _partir_llm(spec: str) -> tuple[str, Optional[str]]:
    """'ollama:qwen2.5:7b' → ('ollama', 'qwen2.5:7b'); 'gemini' → ('gemini', None)."""
    backend, _, modelo = spec.partition(":")
    return backend.strip(), (modelo.strip() or None)


def _mensaje_desde_fichero(ruta: Path, fecha: datetime, remitente: str | None, vocab: list[str], stt: Optional[str]) -> Mensaje:
    datos = ruta.read_bytes()
    h = hashlib.sha256(datos).hexdigest()
    ident = "M" + h[:8]
    if es_audio(ruta):
        mostrar.aviso(f"Transcribiendo {ruta.name} con {stt or cfg.stt_backend}…")
        t0 = time.time()
        tr = transcribir(ruta, vocab, stt)
        mostrar.aviso(f"Transcrito en {time.time() - t0:.1f} s ({tr.modelo})")
        return Mensaje(
            id=ident, canal="audio", fecha=fecha, remitente=remitente, texto=tr.texto,
            fichero=str(ruta), hash=h, transcripcion=tr,
        )
    texto = datos.decode("utf-8", errors="replace")
    asunto = None
    if texto.lower().startswith("asunto:"):
        primera, _, resto = texto.partition("\n")
        asunto, texto = primera.split(":", 1)[1].strip(), resto
    return Mensaje(
        id=ident, canal="correo", fecha=fecha, remitente=remitente, asunto=asunto, texto=texto.strip(),
        fichero=str(ruta), hash=h,
    )


def _guardar(mensaje: Mensaje, crudo: str, interp: Interpretacion, tickets: list[Ticket], etiqueta: str) -> Path:
    sufijo = etiqueta.replace(":", "-").replace("/", "-")
    carpeta = cfg.dir_salida / f"{datetime.now():%Y%m%d_%H%M%S}_{mensaje.id}_{sufijo}"
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "mensaje.json").write_text(mensaje.model_dump_json(indent=2), encoding="utf-8")
    (carpeta / "interpretacion_cruda.json").write_text(crudo, encoding="utf-8")
    (carpeta / "interpretacion.json").write_text(interp.model_dump_json(indent=2), encoding="utf-8")
    (carpeta / "tickets.json").write_text(
        json.dumps([t.model_dump(mode="json") for t in tickets], ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return carpeta


def _interpretar_mensaje(mensaje: Mensaje, llm_spec: Optional[str], ruta_interp: Optional[str]):
    """Devuelve (interp, crudo, etiqueta, segundos)."""
    if ruta_interp:
        crudo = Path(ruta_interp).read_text(encoding="utf-8")
        return Interpretacion.model_validate_json(crudo), crudo, f"archivo:{Path(ruta_interp).name}", 0.0
    from .interpretar import interpretar

    backend, modelo = _partir_llm(llm_spec) if llm_spec else (None, None)
    t0 = time.time()
    interp, crudo, etiqueta = interpretar(mensaje.texto, mensaje.fecha, mensaje.remitente, mensaje.canal, backend, modelo)
    return interp, crudo, etiqueta, time.time() - t0


def cmd_procesar(args: argparse.Namespace) -> int:
    ruta = Path(args.fichero)
    if not ruta.exists():
        print(f"No existe {ruta}")
        return 2
    fecha = datetime.fromisoformat(args.fecha) if args.fecha else datetime.now()
    m = M.cargar()
    mostrar.aviso(f"Maestros: {M.resumen(m)}")

    mensaje = _mensaje_desde_fichero(ruta, fecha, args.remitente, M.vocabulario(m), args.stt)
    mostrar.mensaje(mensaje)

    if not args.interpretacion:
        mostrar.aviso(f"Interpretando con {args.llm or cfg.llm_backend}…")
    interp, crudo, etiqueta, segundos = _interpretar_mensaje(mensaje, args.llm, args.interpretacion)
    mostrar.aviso(f"Interpretación de {etiqueta} en {segundos:.1f} s")
    mostrar.interpretacion(interp)

    tickets = construir(mensaje, interp, m)
    for t in tickets:
        mostrar.ticket(t)

    if args.crear:
        from .bc import BC, ErrorBC

        bc = BC()
        for t in tickets:
            if t.tipo != TipoPeticion.pedido:
                continue
            if t.incompleto and not args.forzar:
                mostrar.aviso(f"{t.id}: incompleto (falta {', '.join(t.incompleto)}); no se crea. Usa --forzar para crearlo igualmente.")
                continue
            original = Path(mensaje.fichero) if mensaje.fichero else None
            nombre = f"Ordena {mensaje.id} - {original.name}" if original else None
            try:
                res = bc.crear_pedido(t, original, nombre)
            except ErrorBC as e:
                mostrar.aviso(f"{t.id}: Business Central no lo aceptó → {e}")
                continue
            t.erp_numero, t.erp_id = res["number"], res["id"]
            mostrar.aviso(
                f"{t.id}: pedido de venta {res['number']} "
                + ("ya existía (mismo número de documento externo)" if res["ya_existia"] else "creado sin registrar en Business Central")
            )
            if res.get("adjunto"):
                mostrar.aviso(f"{t.id}: original adjunto al pedido{' (ya estaba)' if res.get('adjunto_ya_existia') else ''}: {res['adjunto']}")
            if res.get("adjunto_error"):
                mostrar.aviso(f"{t.id}: no se pudo adjuntar el original → {res['adjunto_error']}")
            mostrar.aviso(f"{t.id}: abrir en Business Central → {res['url']}")

    carpeta = _guardar(mensaje, crudo, interp, tickets, etiqueta)
    mostrar.aviso(f"Guardado en {carpeta}")
    return 0


def _resumen_ticket(t: Ticket) -> str:
    cli = t.cliente.valor or "?"
    lineas = "; ".join(
        f"{l.cantidad:g}×{l.articulo.valor or '?'}" if l.cantidad is not None else f"?×{l.articulo.valor or '?'}"
        for l in t.lineas
    )
    fecha = t.fecha_entrega.valor or (f"'{t.fecha_entrega.tal_cual}'" if t.fecha_entrega.tal_cual else "—")
    extra = []
    if t.incompleto:
        extra.append("INCOMPLETO")
    if t.dudosos:
        extra.append(f"{len(t.dudosos)} dudosos")
    return f"{t.tipo.value} · cli {cli} · [{lineas or '—'}] · fecha {fecha}" + (f" · {' '.join(extra)}" if extra else "")


def cmd_comparar(args: argparse.Namespace) -> int:
    """El mismo mensaje por varios transcriptores y varios modelos. La tabla es el techo frente a lo local."""
    from rich import box
    from rich.table import Table

    ruta = Path(args.fichero)
    if not ruta.exists():
        print(f"No existe {ruta}")
        return 2
    fecha = datetime.fromisoformat(args.fecha) if args.fecha else datetime.now()
    m = M.cargar()
    vocab = M.vocabulario(m)
    stts = [s.strip() for s in args.stt.split(",") if s.strip()] if es_audio(ruta) else ["—"]
    llms = [s.strip() for s in args.llm.split(",") if s.strip()]

    filas = []
    for stt in stts:
        mensaje = _mensaje_desde_fichero(ruta, fecha, args.remitente, vocab, None if stt == "—" else stt)
        if mensaje.transcripcion:
            mostrar.mensaje(mensaje)
        for llm in llms:
            try:
                interp, crudo, etiqueta, segundos = _interpretar_mensaje(mensaje, llm, None)
            except SystemExit as e:
                filas.append((stt, llm, "ERROR", str(e).splitlines()[0][:80], ""))
                continue
            tickets = construir(mensaje, interp, m)
            carpeta = _guardar(mensaje, crudo, interp, tickets, f"{stt}_{etiqueta}")
            filas.append((stt, etiqueta, f"{segundos:.1f} s", "\n".join(_resumen_ticket(t) for t in tickets), carpeta.name))
            if args.detalle:
                for t in tickets:
                    mostrar.ticket(t)

    # Una línea de cabecera por combinación y debajo un ticket por línea: legible en cualquier ancho.
    mostrar.consola.rule(f"Comparación · {ruta.name}")
    for stt, etiqueta, tiempo, resumen, salida in filas:
        mostrar.consola.print(f"[bold]{stt}[/bold] · [bold]{etiqueta}[/bold] · {tiempo}  [dim]{salida}[/dim]")
        for linea in resumen.splitlines():
            estilo = "red" if linea == "ERROR" or "INCOMPLETO" in linea else ""
            mostrar.consola.print(f"    {linea}", style=estilo)
    return 0


def cmd_transcribir(args: argparse.Namespace) -> int:
    m = M.cargar()
    tr = transcribir(Path(args.fichero), M.vocabulario(m), args.stt)
    for s in tr.segmentos:
        marca = " ⚠" if s.dudoso else ""
        print(f"[{s.inicio:6.1f} - {s.fin:6.1f}] {s.texto}{marca}")
    print(f"\n{tr.texto}\n\n({tr.modelo}, {tr.duracion:.1f} s)")
    return 0


def cmd_maestros(args: argparse.Namespace) -> int:
    from .bc import BC

    bc = BC()
    mostrar.aviso(f"Empresa: {bc.empresa_id()}")
    m = M.desde_bc(bc.clientes(), bc.articulos())
    M.guardar(m, M.ruta_bc())
    ruta_vocab = M.guardar_vocabulario(m)
    mostrar.aviso(f"Descargados {M.resumen(m)} → {M.ruta_bc()}")
    mostrar.aviso(f"Vocabulario para Whisper → {ruta_vocab}")
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    from .web.app import servir

    servir(args.host, args.puerto)
    return 0


def cmd_probar_bc(args: argparse.Namespace) -> int:
    from .bc import BC

    bc = BC()
    for e in bc.empresas():
        print(f"{e.get('id')}  {e.get('name')}  ({e.get('displayName')})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ordena-poc", description="Ordena · prueba de concepto")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("procesar", help="mensaje (texto o audio) → tickets [→ pedido en Business Central]")
    s.add_argument("fichero")
    s.add_argument("--remitente", help="correo del remitente, si se conoce (resuelve el cliente por la ficha)")
    s.add_argument("--fecha", help="fecha del mensaje, ISO (por defecto ahora); las fechas relativas se calculan desde aquí")
    s.add_argument("--interpretacion", help="JSON de interpretación ya hecha: salta el modelo")
    s.add_argument("--llm", help="proveedor[:modelo]: ollama:qwen2.5:7b, gemini, gemini:gemini-2.5-pro, groq (por defecto, el de .env)")
    s.add_argument("--stt", help="transcriptor: local | groq (por defecto, el de .env)")
    s.add_argument("--crear", action="store_true", help="crear los pedidos validables en Business Central (sin registrar)")
    s.add_argument("--forzar", action="store_true", help="crear también los tickets incompletos")
    s.set_defaults(fn=cmd_procesar)

    s = sub.add_parser("comparar", help="el mismo mensaje por varios transcriptores y modelos, en una tabla")
    s.add_argument("fichero")
    s.add_argument("--remitente")
    s.add_argument("--fecha")
    s.add_argument("--stt", default="local,groq", help="lista separada por comas (solo audio)")
    s.add_argument("--llm", default="ollama:qwen2.5:7b,ollama:qwen2.5:14b,gemini,groq", help="lista separada por comas")
    s.add_argument("--detalle", action="store_true", help="imprimir también cada ticket")
    s.set_defaults(fn=cmd_comparar)

    s = sub.add_parser("transcribir", help="solo transcribir un audio")
    s.add_argument("fichero")
    s.add_argument("--stt", help="local | groq")
    s.set_defaults(fn=cmd_transcribir)

    s = sub.add_parser("maestros", help="descargar clientes y artículos de Business Central")
    s.set_defaults(fn=cmd_maestros)

    s = sub.add_parser("probar-bc", help="listar las empresas del entorno (prueba de autenticación)")
    s.set_defaults(fn=cmd_probar_bc)

    s = sub.add_parser("web", help="la bandeja con pinta de Navision, en local")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--puerto", type=int, default=8765)
    s.set_defaults(fn=cmd_web)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
