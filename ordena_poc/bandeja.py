"""La bandeja: mensajes y tickets de verdad, persistidos en SQLite, con estados e historial.

Un hilo procesa los mensajes de uno en uno (la GPU es una). La pantalla solo
lee y cambia estados. Nadie borra nada.
"""
from __future__ import annotations

import hashlib
import json
import queue
import re
import sqlite3
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from . import maestros as M
from .config import cfg
from .esquema import Ticket
from .tickets import construir
from .transcribir import es_audio

DIR = cfg.dir_datos.parent / "bandeja"
DB = DIR / "bandeja.db"
ORIGINALES = DIR / "originales"

ESQUEMA_SQL = """
CREATE TABLE IF NOT EXISTS mensajes (
  id TEXT PRIMARY KEY, numero INTEGER, canal TEXT, fecha TEXT, remitente TEXT, nombre_fichero TEXT,
  ruta TEXT, hash TEXT, texto TEXT, transcripcion TEXT, estado TEXT, error TEXT, etiqueta_modelo TEXT,
  creado TEXT, procesado TEXT
);
CREATE TABLE IF NOT EXISTS tickets (
  numero INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE, mensaje_id TEXT, tipo TEXT, familia TEXT,
  estado TEXT, asunto TEXT, cliente_valor TEXT, cliente_etiqueta TEXT, incompleto INTEGER, n_dudosos INTEGER,
  json TEXT, motivo TEXT, erp_numero TEXT, creado TEXT, actualizado TEXT
);
CREATE TABLE IF NOT EXISTS historial (
  n INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT, cuando TEXT, quien TEXT, accion TEXT, detalle TEXT
);
"""

MOTIVOS_RECHAZO = ["duplicado", "no es un pedido", "cliente desconocido", "artículo inexistente", "otro"]

# Transiciones permitidas. Registrar en el ERP lo hace una persona en el ERP; aquí "escrito" es sin registrar.
TRANSICIONES = {
    "pedidos": {"validar": ("pendiente", "validado"), "rechazar": ("pendiente", "rechazado"),
                "escribir": ("validado", "escrito"), "reabrir": ("rechazado", "pendiente")},
    "otros": {"cerrar": ("pendiente", "cerrado"), "reabrir": ("cerrado", "pendiente")},
}


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _url_erp(numero: Optional[str]) -> Optional[str]:
    if not numero or not cfg.bc_configurado:
        return None
    from .bc import url_pedido

    return url_pedido(cfg, numero)


def _nombre_seguro(nombre: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", nombre)[:80] or "mensaje"


class Bandeja:
    def __init__(self) -> None:
        DIR.mkdir(parents=True, exist_ok=True)
        ORIGINALES.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(DB, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(ESQUEMA_SQL)
        self.lock = threading.Lock()
        self.cola: queue.Queue = queue.Queue()
        self.maestros = M.cargar()
        self.procesando: Optional[str] = None
        self.fase: str = ""
        # Lo que se quedó a medias en una sesión anterior vuelve a la cola.
        for fila in self.con.execute("SELECT id, ruta, remitente, fecha FROM mensajes WHERE estado IN ('en_cola','en_proceso')"):
            self.cola.put((fila["id"], Path(fila["ruta"]), fila["remitente"], fila["fecha"]))
        threading.Thread(target=self._trabajador, daemon=True).start()

    # --- entrada --------------------------------------------------------------

    def recibir_fichero(self, nombre: str, datos: bytes, remitente: Optional[str] = None,
                        fecha: Optional[datetime] = None, canal: Optional[str] = None) -> dict:
        h = hashlib.sha256(datos).hexdigest()
        mid = "M" + h[:8]
        with self.lock:
            existente = self.con.execute("SELECT id, estado FROM mensajes WHERE id=?", (mid,)).fetchone()
            if existente:
                return {"id": mid, "duplicado": True, "estado": existente["estado"]}
            ruta = ORIGINALES / f"{mid}_{_nombre_seguro(nombre)}"
            ruta.write_bytes(datos)
            canal = canal or ("audio" if es_audio(ruta) else "correo")
            fecha = fecha or datetime.now()
            numero = (self.con.execute("SELECT COALESCE(MAX(numero),0) FROM mensajes").fetchone()[0] or 0) + 1
            self.con.execute(
                "INSERT INTO mensajes (id, numero, canal, fecha, remitente, nombre_fichero, ruta, hash, estado, creado) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (mid, numero, canal, fecha.isoformat(timespec="seconds"), remitente or None, nombre, str(ruta), h, "en_cola", _ahora()),
            )
            self.con.commit()
        self.cola.put((mid, ruta, remitente, fecha.isoformat(timespec="seconds")))
        return {"id": mid, "duplicado": False, "estado": "en_cola"}

    def recibir_texto(self, texto: str, remitente: Optional[str] = None, fecha: Optional[datetime] = None) -> dict:
        nombre = f"texto_{datetime.now():%Y%m%d_%H%M%S}.txt"
        return self.recibir_fichero(nombre, texto.encode("utf-8"), remitente, fecha, canal="correo")

    # --- procesamiento --------------------------------------------------------

    def _trabajador(self) -> None:
        while True:
            mid, ruta, remitente, fecha = self.cola.get()
            try:
                self._procesar(mid, ruta, remitente, fecha)
            except Exception:  # nunca se cae el hilo
                traceback.print_exc()
            finally:
                self.cola.task_done()

    def _set_mensaje(self, mid: str, **campos) -> None:
        with self.lock:
            columnas = ", ".join(f"{k}=?" for k in campos)
            self.con.execute(f"UPDATE mensajes SET {columnas} WHERE id=?", (*campos.values(), mid))
            self.con.commit()

    def _procesar(self, mid: str, ruta: Path, remitente: Optional[str], fecha_iso: Optional[str]) -> None:
        from .main import _interpretar_mensaje, _mensaje_desde_fichero  # import tardío: evita el ciclo

        self.procesando, self.fase = mid, "transcribiendo" if es_audio(ruta) else "leyendo"
        self._set_mensaje(mid, estado="en_proceso", error=None)
        try:
            fecha = datetime.fromisoformat(fecha_iso) if fecha_iso else datetime.now()
            mensaje = _mensaje_desde_fichero(ruta, fecha, remitente, M.vocabulario(self.maestros), None)
            mensaje.id = mid
            self._set_mensaje(
                mid, texto=mensaje.texto,
                transcripcion=mensaje.transcripcion.model_dump_json() if mensaje.transcripcion else None,
            )
            self.fase = "interpretando"
            interp, crudo, etiqueta, _ = _interpretar_mensaje(mensaje, None, None)
            self.fase = "resolviendo"
            tickets = construir(mensaje, interp, self.maestros)
            with self.lock:
                for t in tickets:
                    familia = "pedidos" if t.exige_validacion else "otros"
                    self.con.execute(
                        "INSERT OR REPLACE INTO tickets (id, mensaje_id, tipo, familia, estado, asunto, cliente_valor, cliente_etiqueta, "
                        "incompleto, n_dudosos, json, creado, actualizado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (t.id, mid, t.tipo.value, familia, "pendiente", t.asunto, t.cliente.valor, t.cliente.etiqueta,
                         1 if t.incompleto else 0, len(t.dudosos), t.model_dump_json(), _ahora(), _ahora()),
                    )
                    self.con.execute(
                        "INSERT INTO historial (ticket_id, cuando, quien, accion, detalle) VALUES (?,?,?,?,?)",
                        (t.id, _ahora(), "Ordena", "creado", f"interpretado por {etiqueta}"),
                    )
                self.con.commit()
            self._set_mensaje(mid, estado="procesado", etiqueta_modelo=etiqueta, procesado=_ahora())
        except SystemExit as e:  # los errores de proveedor se lanzan así en la PoC
            self._set_mensaje(mid, estado="error", error=str(e)[:500])
        except Exception as e:
            self._set_mensaje(mid, estado="error", error=f"{type(e).__name__}: {e}"[:500])
            traceback.print_exc()
        finally:
            self.procesando, self.fase = None, ""

    # --- lectura ----------------------------------------------------------------

    def tickets(self, familia: Optional[str] = None) -> list[dict]:
        sql = "SELECT t.*, m.fecha AS fecha_mensaje, m.canal FROM tickets t JOIN mensajes m ON m.id=t.mensaje_id"
        params: tuple = ()
        if familia in ("pedidos", "otros"):
            sql += " WHERE t.familia=?"
            params = (familia,)
        sql += " ORDER BY t.numero DESC"
        with self.lock:
            filas = self.con.execute(sql, params).fetchall()
        return [
            {k: fila[k] for k in fila.keys() if k != "json"}
            | {"numero_texto": f"T{fila['numero']:05d}", "erp_url": _url_erp(fila["erp_numero"])}
            for fila in filas
        ]

    def ticket(self, tid: str) -> Optional[dict]:
        with self.lock:
            fila = self.con.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
            if not fila:
                return None
            mensaje = self.con.execute("SELECT * FROM mensajes WHERE id=?", (fila["mensaje_id"],)).fetchone()
            historial = self.con.execute("SELECT * FROM historial WHERE ticket_id=? ORDER BY n", (tid,)).fetchall()
        t = json.loads(fila["json"])
        return {
            "numero": fila["numero"], "numero_texto": f"T{fila['numero']:05d}", "estado": fila["estado"],
            "familia": fila["familia"], "motivo": fila["motivo"], "erp_numero": fila["erp_numero"],
            "erp_url": _url_erp(fila["erp_numero"]),
            "creado": fila["creado"], "actualizado": fila["actualizado"], "ticket": t,
            "mensaje": {
                "id": mensaje["id"], "canal": mensaje["canal"], "fecha": mensaje["fecha"], "remitente": mensaje["remitente"],
                "nombre_fichero": mensaje["nombre_fichero"], "texto": mensaje["texto"], "etiqueta_modelo": mensaje["etiqueta_modelo"],
                "transcripcion": json.loads(mensaje["transcripcion"]) if mensaje["transcripcion"] else None,
            },
            "historial": [dict(h) for h in historial],
        }

    def mensajes(self) -> list[dict]:
        with self.lock:
            filas = self.con.execute(
                "SELECT m.*, (SELECT COUNT(*) FROM tickets t WHERE t.mensaje_id=m.id) AS n_tickets "
                "FROM mensajes m ORDER BY m.numero DESC"
            ).fetchall()
        return [{k: f[k] for k in f.keys() if k not in ("texto", "transcripcion", "ruta")} for f in filas]

    def ruta_original(self, mid: str) -> Optional[Path]:
        with self.lock:
            fila = self.con.execute("SELECT ruta FROM mensajes WHERE id=?", (mid,)).fetchone()
        return Path(fila["ruta"]) if fila else None

    def estado(self) -> dict:
        with self.lock:
            cuenta = {
                f"{fila['familia']}_{fila['estado']}": fila["n"]
                for fila in self.con.execute("SELECT familia, estado, COUNT(*) AS n FROM tickets GROUP BY familia, estado")
            }
            n_mensajes = self.con.execute("SELECT COUNT(*) FROM mensajes").fetchone()[0]
            en_cola = self.con.execute("SELECT COUNT(*) FROM mensajes WHERE estado IN ('en_cola','en_proceso')").fetchone()[0]
        return {
            "cuenta": cuenta, "mensajes": n_mensajes, "en_cola": en_cola,
            "procesando": self.procesando, "fase": self.fase,
            "modelo": f"{cfg.llm_backend}:{ {'ollama': cfg.llm_modelo, 'gemini': cfg.gemini_modelo, 'groq': cfg.groq_modelo}[cfg.llm_backend] }",
            "transcriptor": cfg.stt_backend if cfg.stt_backend != "local" else f"local:{cfg.whisper_modelo}",
            "bc_configurado": cfg.bc_configurado, "maestros": M.resumen(self.maestros),
        }

    # --- acciones ---------------------------------------------------------------

    def accion(self, tid: str, accion: str, quien: str = "administración", motivo: Optional[str] = None) -> dict:
        with self.lock:
            fila = self.con.execute("SELECT * FROM tickets WHERE id=?", (tid,)).fetchone()
        if not fila:
            raise KeyError(tid)
        permitidas = TRANSICIONES[fila["familia"]]
        if accion not in permitidas:
            raise ValueError(f"'{accion}' no existe para un ticket de {fila['familia']}")
        desde, hasta = permitidas[accion]
        if fila["estado"] != desde:
            raise ValueError(f"el ticket está en '{fila['estado']}', no en '{desde}'")
        if accion == "rechazar" and not motivo:
            raise ValueError("rechazar necesita un motivo")

        detalle = motivo or ""
        erp_numero = fila["erp_numero"]
        ticket_json = fila["json"]
        if accion == "escribir":
            from .bc import BC, ErrorBC

            t = Ticket.model_validate_json(ticket_json)
            if not cfg.bc_configurado:
                raise ValueError("Business Central no está configurado (BC_TENANT_ID y BC_CLIENT_ID en .env)")
            with self.lock:
                msj = self.con.execute("SELECT ruta, nombre_fichero FROM mensajes WHERE id=?", (fila["mensaje_id"],)).fetchone()
            original = Path(msj["ruta"]) if msj and msj["ruta"] else None
            nombre = f"Ordena {fila['mensaje_id']} - {msj['nombre_fichero']}" if msj else None
            try:
                res = BC().crear_pedido(t, original, nombre)
            except ErrorBC as e:
                raise ValueError(str(e)) from e
            erp_numero = res["number"]
            t.erp_numero, t.erp_id = res["number"], res["id"]
            ticket_json = t.model_dump_json()
            detalle = f"pedido de venta {erp_numero}" + (" (ya existía)" if res["ya_existia"] else " creado sin registrar")
            if res.get("adjunto"):
                detalle += " · original adjunto" + (" (ya estaba)" if res.get("adjunto_ya_existia") else "")
            if res.get("adjunto_error"):
                detalle += f" · NO se pudo adjuntar el original: {res['adjunto_error']}"

        with self.lock:
            self.con.execute(
                "UPDATE tickets SET estado=?, motivo=?, erp_numero=?, json=?, actualizado=? WHERE id=?",
                (hasta, motivo if accion == "rechazar" else fila["motivo"], erp_numero, ticket_json, _ahora(), tid),
            )
            self.con.execute(
                "INSERT INTO historial (ticket_id, cuando, quien, accion, detalle) VALUES (?,?,?,?,?)",
                (tid, _ahora(), quien, accion, detalle),
            )
            self.con.commit()
        return {"id": tid, "estado": hasta, "erp_numero": erp_numero, "detalle": detalle}
