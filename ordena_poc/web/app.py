"""API y estáticos de la bandeja. FastAPI, sin base de datos de negocio: solo tickets."""
from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..bandeja import MOTIVOS_RECHAZO, Bandeja

ESTATICOS = Path(__file__).parent / "static"

app = FastAPI(title="Ordena · bandeja", docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
_bandeja: Optional[Bandeja] = None


def bandeja() -> Bandeja:
    global _bandeja
    if _bandeja is None:
        _bandeja = Bandeja()
    return _bandeja


def _fecha(valor: str) -> Optional[datetime]:
    return datetime.fromisoformat(valor) if valor else None


@app.get("/", response_class=HTMLResponse)
def inicio() -> str:
    return (ESTATICOS / "index.html").read_text(encoding="utf-8")


@app.get("/api/estado")
def estado() -> dict:
    return bandeja().estado()


@app.get("/api/motivos")
def motivos() -> list[str]:
    return MOTIVOS_RECHAZO


@app.get("/api/tickets")
def tickets(familia: Optional[str] = None) -> list[dict]:
    return bandeja().tickets(familia)


@app.get("/api/tickets/{tid}")
def ticket(tid: str) -> dict:
    t = bandeja().ticket(tid)
    if not t:
        raise HTTPException(404, "no existe ese ticket")
    return t


class Accion(BaseModel):
    motivo: Optional[str] = None
    quien: str = "administración"


@app.post("/api/tickets/{tid}/{accion}")
def accion(tid: str, accion: str, cuerpo: Optional[Accion] = None) -> dict:
    cuerpo = cuerpo or Accion()
    try:
        return bandeja().accion(tid, accion, cuerpo.quien, cuerpo.motivo)
    except KeyError:
        raise HTTPException(404, "no existe ese ticket")
    except ValueError as e:
        raise HTTPException(409, str(e))


@app.get("/api/mensajes")
def mensajes() -> list[dict]:
    return bandeja().mensajes()


@app.post("/api/mensajes")
async def subir(fichero: UploadFile = File(...), remitente: str = Form(""), fecha: str = Form("")) -> dict:
    datos = await fichero.read()
    if not datos:
        raise HTTPException(400, "archivo vacío")
    return bandeja().recibir_fichero(fichero.filename or "mensaje", datos, remitente or None, _fecha(fecha))


class Texto(BaseModel):
    texto: str
    remitente: Optional[str] = None
    fecha: Optional[str] = None


@app.post("/api/mensajes/texto")
def texto(cuerpo: Texto) -> dict:
    if not cuerpo.texto.strip():
        raise HTTPException(400, "texto vacío")
    return bandeja().recibir_texto(cuerpo.texto, cuerpo.remitente or None, _fecha(cuerpo.fecha or ""))


@app.get("/api/originales/{mid}")
def original(mid: str):
    ruta = bandeja().ruta_original(mid)
    if not ruta or not ruta.exists():
        raise HTTPException(404, "no hay original")
    tipo, _ = mimetypes.guess_type(ruta.name)
    if ruta.suffix.lower() == ".ogg":
        tipo = "audio/ogg"
    return FileResponse(ruta, media_type=tipo or "application/octet-stream", filename=ruta.name)


def servir(host: str = "127.0.0.1", puerto: int = 8765) -> None:
    import uvicorn

    bandeja()  # arranca el hilo de proceso antes de aceptar peticiones
    print(f"Ordena · bandeja en http://{host}:{puerto}")
    uvicorn.run(app, host=host, port=puerto, log_level="warning")
