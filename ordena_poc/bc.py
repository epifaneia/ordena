"""Adaptador de Business Central online (API v2.0).

Es el adaptador "de mañana". El de hoy, Navision por SOAP, tendrá la misma
entrada (un Ticket validado) y vivirá al lado como `nav.py`.

Autenticación por Entra ID con MSAL:
- sin secreto: inicio de sesión de usuario por código de dispositivo (PoC);
- con secreto: credenciales de aplicación, el "usuario de servicio" de producción.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import requests

from .config import Config, cfg
from .esquema import Ticket

SCOPE = "https://api.businesscentral.dynamics.com/.default"
# Valor del enum de la API v2.0 para "Pedido de venta" como padre de un adjunto (sale del $metadata).
PADRE_PEDIDO_VENTA = "Sales_x0020_Order"


class ErrorBC(RuntimeError):
    pass


def url_pedido(config: Config, numero: str) -> str:
    """Enlace al pedido de venta en el cliente web de Business Central (página 42, filtrada por número).
    No necesita token: se calcula con el tenant, el entorno y la empresa."""
    url = f"https://businesscentral.dynamics.com/{config.bc_tenant}/{config.bc_environment}/?"
    if config.bc_company:
        url += f"company={quote(config.bc_company)}&"
    return url + f"page=42&filter={quote(f"'No.' IS '{numero}'")}"


class BC:
    def __init__(self, config: Config = cfg):
        if not config.bc_configurado:
            raise SystemExit("Business Central no está configurado: rellena BC_TENANT_ID y BC_CLIENT_ID en .env")
        self.cfg = config
        self.sesion = requests.Session()
        self._empresa_id: Optional[str] = None
        self.sesion.headers["Authorization"] = f"Bearer {self._token()}"
        self.sesion.headers["Accept"] = "application/json"

    # --- autenticación ------------------------------------------------------

    def _token(self) -> str:
        import msal

        autoridad = f"https://login.microsoftonline.com/{self.cfg.bc_tenant}"
        if self.cfg.bc_client_secret:
            app = msal.ConfidentialClientApplication(
                self.cfg.bc_client_id, client_credential=self.cfg.bc_client_secret, authority=autoridad
            )
            res = app.acquire_token_for_client(scopes=[SCOPE])
        else:
            self.cfg.dir_cache.mkdir(parents=True, exist_ok=True)
            ruta_cache = self.cfg.dir_cache / "msal.json"
            cache = msal.SerializableTokenCache()
            if ruta_cache.exists():
                cache.deserialize(ruta_cache.read_text(encoding="utf-8"))
            app = msal.PublicClientApplication(self.cfg.bc_client_id, authority=autoridad, token_cache=cache)
            cuentas = app.get_accounts()
            res = app.acquire_token_silent([SCOPE], account=cuentas[0]) if cuentas else None
            if not res:
                flujo = app.initiate_device_flow(scopes=[SCOPE])
                if "user_code" not in flujo:
                    raise ErrorBC(f"No se pudo iniciar el login por código de dispositivo: {flujo}")
                print(flujo["message"])  # "Ve a https://microsoft.com/devicelogin y escribe el código ..."
                res = app.acquire_token_by_device_flow(flujo)
            if cache.has_state_changed:
                ruta_cache.write_text(cache.serialize(), encoding="utf-8")
        if "access_token" not in res:
            raise ErrorBC(f"Sin token: {res.get('error')} · {res.get('error_description')}")
        return res["access_token"]

    # --- http ---------------------------------------------------------------

    def _url(self, ruta: str) -> str:
        return f"{self.cfg.bc_base_url}/{ruta.lstrip('/')}"

    def get(self, ruta: str, params: Optional[dict] = None) -> Any:
        r = self.sesion.get(self._url(ruta), params=params, timeout=60)
        self._comprobar(r)
        datos = r.json()
        return datos.get("value", datos)

    def post(self, ruta: str, cuerpo: dict) -> Any:
        r = self.sesion.post(self._url(ruta), json=cuerpo, timeout=60, headers={"Content-Type": "application/json"})
        self._comprobar(r)
        return r.json()

    @staticmethod
    def _comprobar(r: requests.Response) -> None:
        if r.ok:
            return
        try:
            err = r.json().get("error", {})
            mensaje = f"{err.get('code')}: {err.get('message')}"
        except Exception:
            mensaje = r.text[:500]
        raise ErrorBC(f"Business Central respondió {r.status_code} · {mensaje}")

    # --- empresa y maestros -------------------------------------------------

    def empresas(self) -> list[dict]:
        return self.get("companies")

    def empresa_id(self) -> str:
        if self._empresa_id:
            return self._empresa_id
        empresas = self.empresas()
        if not empresas:
            raise ErrorBC("El entorno no tiene empresas")
        elegida = empresas[0]
        if self.cfg.bc_company:
            elegida = next(
                (e for e in empresas if e.get("name", "").lower() == self.cfg.bc_company.lower()), None
            ) or elegida
        self._empresa_id = elegida["id"]
        return self._empresa_id

    def _ruta_empresa(self, recurso: str) -> str:
        return f"companies({self.empresa_id()})/{recurso}"

    def clientes(self) -> list[dict]:
        return self.get(
            self._ruta_empresa("customers"),
            {"$select": "id,number,displayName,email,phoneNumber,salespersonCode,addressLine1,city,postalCode", "$top": "5000"},
        )

    def articulos(self) -> list[dict]:
        return self.get(
            self._ruta_empresa("items"),
            {"$select": "id,number,displayName,type,baseUnitOfMeasureCode,unitPrice,blocked", "$top": "5000"},
        )

    # --- escritura: pedido de venta sin registrar ---------------------------

    def cuerpo_pedido(self, t: Ticket) -> dict:
        if not t.cliente.valor:
            raise ErrorBC("El ticket no tiene cliente resuelto")
        lineas = []
        for l in t.lineas:
            if not l.articulo.valor or l.cantidad is None:
                raise ErrorBC(f"Línea sin artículo o sin cantidad: '{l.original.descripcion_tal_cual}'")
            linea = {"lineType": "Item", "lineObjectNumber": l.articulo.valor, "quantity": l.cantidad}
            if l.unidad.valor:
                linea["unitOfMeasureCode"] = l.unidad.valor
            lineas.append(linea)
        cuerpo: dict = {
            "customerNumber": t.cliente.valor,
            # El número de documento externo es el enlace del pedido con el ticket:
            # quien abra el pedido en el ERP ve de qué ticket vino, y no se escribe dos veces.
            "externalDocumentNumber": t.id[:35],
            "salesOrderLines": lineas,
        }
        if t.fecha_entrega.valor:
            cuerpo["requestedDeliveryDate"] = t.fecha_entrega.valor
        return cuerpo

    def pedido_por_referencia(self, referencia: str) -> Optional[dict]:
        res = self.get(self._ruta_empresa("salesOrders"), {"$filter": f"externalDocumentNumber eq '{referencia}'"})
        return res[0] if res else None

    def crear_pedido(self, t: Ticket, original: Optional[Path] = None, nombre_original: Optional[str] = None) -> dict:
        """Crea el pedido sin registrar, o encuentra el que ya existe con la referencia del ticket,
        y le adjunta el mensaje original. Un fallo al adjuntar no tumba el pedido: se devuelve
        en `adjunto_error` para que quede en el historial y lo vea una persona."""
        existente = self.pedido_por_referencia(t.id[:35])
        if existente:
            res = {"number": existente["number"], "id": existente["id"], "ya_existia": True}
        else:
            nuevo = self.post(self._ruta_empresa("salesOrders"), self.cuerpo_pedido(t))
            res = {"number": nuevo.get("number"), "id": nuevo.get("id"), "ya_existia": False}
        res["url"] = url_pedido(self.cfg, res["number"])
        if original is not None and original.exists():
            try:
                adj = self.adjuntar_a_pedido(res["id"], original, nombre_original)
                res["adjunto"], res["adjunto_ya_existia"] = adj["fileName"], adj["ya_existia"]
            except ErrorBC as e:
                res["adjunto_error"] = str(e)
        return res

    # --- adjuntos: el original viaja con el pedido -------------------------

    def adjuntos_pedido(self, pedido_id: str) -> list[dict]:
        return self.get(self._ruta_empresa(f"salesOrders({pedido_id})/documentAttachments"), {"$select": "id,fileName,byteSize"})

    def adjuntar_a_pedido(self, pedido_id: str, ruta: Path, nombre: Optional[str] = None) -> dict:
        """Adjunta un archivo al pedido de venta. Idempotente por nombre: si ya está, no lo repite."""
        nombre = (nombre or ruta.name)[:250]
        ya = next((a for a in self.adjuntos_pedido(pedido_id) if a.get("fileName") == nombre), None)
        if ya:
            return {"id": ya["id"], "fileName": nombre, "ya_existia": True}
        adj = self.post(
            self._ruta_empresa("documentAttachments"),
            {"fileName": nombre, "parentType": PADRE_PEDIDO_VENTA, "parentId": pedido_id},
        )
        datos = ruta.read_bytes()
        url_contenido = self._url(self._ruta_empresa(f"documentAttachments({adj['id']})/attachmentContent"))
        r = self.sesion.patch(
            url_contenido, data=datos, headers={"If-Match": "*", "Content-Type": "application/octet-stream"}, timeout=120
        )
        self._comprobar(r)
        # Guardarraíl: el original tiene que llegar entero. Se lee de vuelta y se compara el tamaño,
        # porque el campo byteSize de la API se queda en 0 aunque el contenido esté.
        vuelta = self.sesion.get(url_contenido, timeout=120)
        self._comprobar(vuelta)
        if len(vuelta.content) != len(datos):
            raise ErrorBC(f"el adjunto llegó incompleto: {len(vuelta.content)} de {len(datos)} bytes")
        return {"id": adj["id"], "fileName": nombre, "ya_existia": False}


def volcar(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)
