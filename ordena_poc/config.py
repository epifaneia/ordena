"""Configuración por variables de entorno (.env en la raíz del repo). Nada de secretos en el código.

La nube (Gemini, Groq) solo se usa como techo de comparación con los datos de
demostración de Microsoft (CRONUS), y hay que pedirla de forma explícita.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent  # raíz del repo
load_dotenv(RAIZ / ".env")


def _lista(valor: str) -> list[str]:
    return [x.strip() for x in valor.split(",") if x.strip()]


@dataclass
class Config:
    bc_tenant: str = os.getenv("BC_TENANT_ID", "")
    bc_environment: str = os.getenv("BC_ENVIRONMENT", "Production")
    bc_company: str = os.getenv("BC_COMPANY", "")
    bc_client_id: str = os.getenv("BC_CLIENT_ID", "")
    bc_client_secret: str = os.getenv("BC_CLIENT_SECRET", "")

    # Interpretación: ollama (local, por defecto) | gemini | groq
    llm_backend: str = os.getenv("ORDENA_LLM_BACKEND", "ollama")
    llm_url: str = os.getenv("ORDENA_LLM_URL", "http://localhost:11434").rstrip("/")
    llm_modelo: str = os.getenv("ORDENA_LLM_MODELO", "qwen2.5:7b")
    gemini_modelo: str = os.getenv("ORDENA_GEMINI_MODELO", "gemini-2.5-flash")
    groq_modelo: str = os.getenv("ORDENA_GROQ_MODELO", "openai/gpt-oss-120b")
    gemini_key: str = os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
    groq_key: str = os.getenv("GROQ_API_KEY", "")

    # Transcripción: local (faster-whisper, por defecto) | groq (Whisper en la nube, techo)
    stt_backend: str = os.getenv("ORDENA_STT_BACKEND", "local")
    whisper_modelo: str = os.getenv("ORDENA_WHISPER_MODELO", "large-v3-turbo")
    whisper_device: str = os.getenv("ORDENA_WHISPER_DEVICE", "cuda")
    whisper_compute: str = os.getenv("ORDENA_WHISPER_COMPUTE", "int8_float16")
    groq_stt_modelo: str = os.getenv("ORDENA_GROQ_STT_MODELO", "whisper-large-v3")

    campos_obligatorios: list[str] = field(
        default_factory=lambda: _lista(
            os.getenv("ORDENA_CAMPOS_OBLIGATORIOS", "cliente,lineas,cantidad,fecha_entrega")
        )
    )

    dir_datos: Path = RAIZ / "data"
    dir_salida: Path = RAIZ / "salida"
    dir_cache: Path = RAIZ / ".cache"

    @property
    def bc_configurado(self) -> bool:
        return bool(self.bc_tenant and self.bc_client_id)

    @property
    def bc_base_url(self) -> str:
        return (
            f"https://api.businesscentral.dynamics.com/v2.0/"
            f"{self.bc_tenant}/{self.bc_environment}/api/v2.0"
        )


cfg = Config()
