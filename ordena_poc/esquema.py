"""El esquema cerrado de Ordena.

Dos mitades. `Interpretacion` es lo único que rellena el modelo: copia lo que
ve, no inventa códigos. Todo lo demás (`Mensaje`, `CampoResuelto`, `Ticket`)
lo construye el código a partir de eso y de los maestros del ERP.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ----------------------------------------------------------------------------
# Lo que devuelve el modelo
# ----------------------------------------------------------------------------


class TipoPeticion(str, Enum):
    pedido = "pedido"
    modificacion = "modificacion"
    consulta = "consulta"
    queja = "queja"
    comentario = "comentario"
    ruido = "ruido"


EXIGEN_VALIDACION = {TipoPeticion.pedido, TipoPeticion.modificacion}


# Nota sobre la salida estructurada: con Ollama, un campo opcional (con valor por
# defecto) es un campo que el modelo puede omitir, y lo omite. Por eso los campos
# que queremos que el modelo se plantee siempre son obligatorios y anulables:
# la clave tiene que estar, el valor puede ser null.


class LineaPedida(BaseModel):
    """Una línea con las palabras del mensaje. Sin códigos: eso lo resuelve el código."""

    descripcion_tal_cual: str = Field(description="El artículo con las palabras exactas del mensaje")
    cantidad: Optional[float] = Field(description="Número, también si viene en letras ('dos' → 2); null solo si no se dice")
    unidad_tal_cual: Optional[str] = Field(
        description="palé, caja, unidades, kilos... con las palabras del mensaje; null si no se dice"
    )
    precio_mencionado: Optional[float] = Field(description="Solo si el mensaje dice un precio; si no, null")
    referencia_mencionada: Optional[str] = Field(description="Código o referencia que el propio mensaje cite; si no, null")
    destino_tal_cual: Optional[str] = Field(
        description="Solo si ESTA línea va a un sitio distinto del resto (otra tienda, nave, dirección o empresa), con las palabras del mensaje; si todo va al mismo sitio, null"
    )
    duda: Optional[str] = Field(description="Si algo de la línea no está claro, decir qué; si no, null")


class Peticion(BaseModel):
    tipo: TipoPeticion
    asunto: str = Field(description="Una línea corta para la lista, en español")
    resumen: str = Field(description="Qué se pide o se dice, en dos o tres frases")
    tercero_tal_cual: Optional[str] = Field(description="Cliente o empresa tal como se nombra en el mensaje; null si no se nombra")
    contacto_tal_cual: Optional[str] = Field(description="Persona que pide, tal como se nombra; null si no")
    direccion_entrega_tal_cual: Optional[str] = Field(description="Dirección o tienda de entrega, tal cual; null si no")
    fecha_entrega_tal_cual: Optional[str] = Field(
        description="'el jueves', '15 de octubre', 'lo antes posible'... con las palabras del mensaje; null si no se dice"
    )
    referencia_cliente: Optional[str] = Field(description="Número de pedido del cliente, si lo da; null si no")
    se_refiere_a_tal_cual: Optional[str] = Field(
        description="Para modificaciones y consultas: a qué pedido o envío anterior se refiere, tal cual; null si no"
    )
    lineas: list[LineaPedida] = Field(description="Para pedidos, modificaciones y consultas de precio; lista vacía si no hay")
    observaciones: Optional[str] = Field(description="Lo que el cliente añade y no es un campo; null si nada")
    campos_dudosos: list[str] = Field(description="Nombres de campos de esta petición que no están claros; lista vacía si ninguno")
    confianza: float = Field(ge=0, le=1, description="1 = seguro, 0 = nada seguro")


class Interpretacion(BaseModel):
    """Salida del modelo. Una, varias o ninguna petición por mensaje."""

    peticiones: list[Peticion] = Field(description="Lista vacía si el mensaje no contiene ninguna petición")
    partes_no_entendidas: list[str] = Field(
        description="Fragmentos del mensaje que NO se han podido interpretar (no lo que sí se ha entendido); lista vacía si ninguno"
    )
    confianza_global: float = Field(ge=0, le=1)


# ----------------------------------------------------------------------------
# Lo que construye el código
# ----------------------------------------------------------------------------


class Segmento(BaseModel):
    inicio: float
    fin: float
    texto: str
    logprob: float
    dudoso: bool


class Transcripcion(BaseModel):
    texto: str
    segmentos: list[Segmento]
    modelo: str
    duracion: float


class Mensaje(BaseModel):
    """La unidad de llegada. Entero, con hash. Nunca se borra ni se edita."""

    id: str
    canal: str  # correo | audio | escaner | arrastrado
    fecha: datetime
    remitente: Optional[str] = None
    asunto: Optional[str] = None
    texto: str
    fichero: Optional[str] = None
    hash: str
    transcripcion: Optional[Transcripcion] = None


class CampoResuelto(BaseModel):
    """Un campo después de pasar por los maestros: código, etiqueta, y si es dudoso."""

    tal_cual: Optional[str] = None
    valor: Optional[str] = None
    etiqueta: Optional[str] = None
    puntuacion: Optional[float] = None
    dudoso: bool = True
    motivo: Optional[str] = None
    candidatos: list[str] = Field(default_factory=list)


class LineaResuelta(BaseModel):
    original: LineaPedida
    articulo: CampoResuelto
    unidad: CampoResuelto
    cantidad: Optional[float]
    precio_tarifa: Optional[float] = None
    dudoso: bool


class Origen(BaseModel):
    mensaje_id: str
    canal: str
    fragmento: Optional[str] = None


class Ticket(BaseModel):
    """La unidad de trabajo. Termina en un solo sitio."""

    id: str
    tipo: TipoPeticion
    exige_validacion: bool
    asunto: str
    resumen: str
    cliente: CampoResuelto
    contacto: Optional[str] = None
    direccion_entrega: CampoResuelto
    fecha_entrega: CampoResuelto
    referencia_cliente: Optional[str] = None
    se_refiere_a: CampoResuelto
    lineas: list[LineaResuelta] = Field(default_factory=list)
    observaciones: Optional[str] = None
    incompleto: list[str] = Field(default_factory=list)
    dudosos: list[str] = Field(default_factory=list)
    confianza: float
    origen: Origen
    hermanos: list[str] = Field(default_factory=list)
    erp_numero: Optional[str] = None
    erp_id: Optional[str] = None
