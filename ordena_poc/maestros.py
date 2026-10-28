"""Maestros del ERP: clientes y artículos.

Regla de Ordena: no se guarda una copia de los maestros. En la PoC se descargan
a un archivo local para poder trabajar sin conexión; en producción se consultan
en el momento, con una caché de minutos.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from .config import cfg


class Cliente(BaseModel):
    numero: str
    nombre: str
    email: Optional[str] = None
    telefono: Optional[str] = None
    vendedor: Optional[str] = None  # código de vendedor: de aquí sale qué comercial ve qué
    direcciones: list[str] = Field(default_factory=list)


class Articulo(BaseModel):
    numero: str
    nombre: str
    unidad_base: Optional[str] = None
    precio: Optional[float] = None
    unidades_alternativas: list[str] = Field(default_factory=list)
    bloqueado: bool = False


class Maestros(BaseModel):
    origen: str
    clientes: list[Cliente]
    articulos: list[Articulo]


def ruta_bc() -> Path:
    return cfg.dir_datos / "maestros_bc.json"


def ruta_demo() -> Path:
    return cfg.dir_datos / "maestros_demo.json"


def cargar() -> Maestros:
    """Los maestros descargados de Business Central si existen; si no, los de demostración."""
    for ruta in (ruta_bc(), ruta_demo()):
        if ruta.exists():
            return Maestros.model_validate_json(ruta.read_text(encoding="utf-8"))
    raise SystemExit("No hay maestros. Ejecuta `maestros` con Business Central configurado, o restaura data/maestros_demo.json.")


def guardar(m: Maestros, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(m.model_dump_json(indent=2), encoding="utf-8")


def vocabulario(m: Maestros) -> list[str]:
    """Nombres que Whisper debería reconocer: artículos y clientes."""
    nombres = [a.nombre for a in m.articulos if not a.bloqueado] + [c.nombre for c in m.clientes]
    # sin duplicados, conservando orden
    vistos: set[str] = set()
    salida: list[str] = []
    for n in nombres:
        if n and n not in vistos:
            vistos.add(n)
            salida.append(n)
    return salida


def guardar_vocabulario(m: Maestros) -> Path:
    ruta = cfg.dir_datos / "vocabulario.txt"
    ruta.write_text("\n".join(vocabulario(m)), encoding="utf-8")
    return ruta


def desde_bc(clientes_json: list[dict], articulos_json: list[dict]) -> Maestros:
    """Convierte las respuestas de la API v2.0 de Business Central al modelo de Ordena."""
    clientes = [
        Cliente(
            numero=c.get("number", ""),
            nombre=c.get("displayName", ""),
            email=(c.get("email") or None),
            telefono=(c.get("phoneNumber") or None),
            vendedor=(c.get("salespersonCode") or None),
            direcciones=[
                ", ".join(
                    x for x in [c.get("addressLine1"), c.get("city"), c.get("postalCode")] if x
                )
            ]
            if c.get("addressLine1")
            else [],
        )
        for c in clientes_json
    ]
    articulos = [
        Articulo(
            numero=a.get("number", ""),
            nombre=a.get("displayName", ""),
            unidad_base=(a.get("baseUnitOfMeasureCode") or None),
            precio=a.get("unitPrice"),
            bloqueado=bool(a.get("blocked", False)),
        )
        for a in articulos_json
        if a.get("type") in (None, "Inventory", "Non_x002D_Inventory", "Non-Inventory", "Service")
    ]
    return Maestros(origen="business-central", clientes=clientes, articulos=articulos)


def resumen(m: Maestros) -> str:
    return f"{len(m.clientes)} clientes y {len(m.articulos)} artículos (origen: {m.origen})"


def a_json(m: Maestros) -> str:
    return json.dumps(m.model_dump(), ensure_ascii=False, indent=2)
