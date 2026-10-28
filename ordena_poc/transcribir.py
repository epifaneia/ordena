"""Transcripción con el vocabulario de los maestros.

- local: faster-whisper en esta máquina. Nada sale. Es lo que correría dentro de la empresa.
- groq: Whisper large-v3 en la nube de Groq. Solo como techo de comparación
  con audios de CRONUS, sin nada confidencial.

Los segmentos con baja confianza se marcan como dudosos y viajan con el
ticket para que la persona escuche y corrija.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .config import cfg
from .esquema import Segmento, Transcripcion

EXTENSIONES_AUDIO = {".m4a", ".mp3", ".wav", ".ogg", ".opus", ".aac", ".flac", ".mp4", ".webm"}


def es_audio(ruta: Path) -> bool:
    return ruta.suffix.lower() in EXTENSIONES_AUDIO


def _prompt(vocabulario: list[str], maximo: int) -> str:
    return (
        "Nota de voz de un cliente haciendo un pedido, en español. "
        "Nombres que pueden aparecer: " + ", ".join(vocabulario[:maximo]) + "."
    )


def _enganchar_cuda() -> None:
    """ctranslate2 busca cublas64_12.dll y cudnn en el PATH. Si están instaladas por pip
    (nvidia-cublas-cu12, nvidia-cudnn-cu12), se añaden sus carpetas bin al buscador de DLL."""
    import importlib.util
    import os

    for paquete in ("nvidia.cublas", "nvidia.cudnn"):
        try:
            spec = importlib.util.find_spec(paquete)
        except (ImportError, ValueError):
            spec = None
        if not spec:
            continue
        base = spec.submodule_search_locations[0] if spec.submodule_search_locations else os.path.dirname(spec.origin or "")
        carpeta = os.path.join(base, "bin")
        if os.path.isdir(carpeta):
            if hasattr(os, "add_dll_directory"):
                os.add_dll_directory(carpeta)
            os.environ["PATH"] = carpeta + os.pathsep + os.environ.get("PATH", "")


def _cargar_modelo():
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:  # pragma: no cover
        raise SystemExit("Falta faster-whisper: pip install -r requirements.txt") from e
    if cfg.whisper_device != "cpu":
        _enganchar_cuda()
    ultimo: Exception | None = None
    # Dos intentos en el dispositivo pedido: la primera descarga del modelo en Windows puede
    # fallar al crear enlaces simbólicos (WinError 1314) y a la segunda ya está en caché.
    for intento in (1, 2):
        try:
            return WhisperModel(cfg.whisper_modelo, device=cfg.whisper_device, compute_type=cfg.whisper_compute), cfg.whisper_device
        except Exception as e:  # librerías CUDA ausentes, GPU ocupada, descarga a medias...
            ultimo = e
            if cfg.whisper_device == "cpu":
                raise
    print(f"[whisper] no se pudo usar {cfg.whisper_device} ({ultimo}); uso cpu/int8")
    return WhisperModel(cfg.whisper_modelo, device="cpu", compute_type="int8"), "cpu"


def transcribir_local(ruta: Path, vocabulario: list[str]) -> Transcripcion:
    modelo, dispositivo = _cargar_modelo()
    segmentos_iter, info = modelo.transcribe(
        str(ruta),
        language="es",
        initial_prompt=_prompt(vocabulario, 60),
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    segmentos = [
        Segmento(
            inicio=round(s.start, 2), fin=round(s.end, 2), texto=s.text.strip(),
            logprob=round(s.avg_logprob, 3), dudoso=(s.avg_logprob < -0.7 or s.no_speech_prob > 0.5),
        )
        for s in segmentos_iter
    ]
    return Transcripcion(
        texto=" ".join(s.texto for s in segmentos).strip(),
        segmentos=segmentos,
        modelo=f"local:{cfg.whisper_modelo} ({dispositivo})",
        duracion=round(float(info.duration or 0.0), 2),
    )


def transcribir_groq(ruta: Path, vocabulario: list[str]) -> Transcripcion:
    if not cfg.groq_key:
        raise SystemExit("Falta GROQ_API_KEY en .env")
    from openai import OpenAI

    cliente = OpenAI(api_key=cfg.groq_key, base_url="https://api.groq.com/openai/v1")
    with open(ruta, "rb") as f:
        r = cliente.audio.transcriptions.create(
            model=cfg.groq_stt_modelo,
            file=f,
            language="es",
            prompt=_prompt(vocabulario, 25),  # el prompt de la API es corto
            response_format="verbose_json",
            temperature=0,
        )

    def _v(seg, clave, defecto=0.0):
        return seg.get(clave, defecto) if isinstance(seg, dict) else getattr(seg, clave, defecto)

    segmentos = []
    for s in (getattr(r, "segments", None) or []):
        logprob = float(_v(s, "avg_logprob", 0.0) or 0.0)
        no_speech = float(_v(s, "no_speech_prob", 0.0) or 0.0)
        segmentos.append(
            Segmento(
                inicio=round(float(_v(s, "start")), 2), fin=round(float(_v(s, "end")), 2),
                texto=str(_v(s, "text", "")).strip(), logprob=round(logprob, 3),
                dudoso=(logprob < -0.7 or no_speech > 0.5),
            )
        )
    texto = (getattr(r, "text", "") or " ".join(s.texto for s in segmentos)).strip()
    duracion = float(getattr(r, "duration", 0.0) or (segmentos[-1].fin if segmentos else 0.0))
    return Transcripcion(texto=texto, segmentos=segmentos, modelo=f"groq:{cfg.groq_stt_modelo}", duracion=round(duracion, 2))


PROVEEDORES_STT = {"local": transcribir_local, "groq": transcribir_groq}


def transcribir(ruta: Path, vocabulario: list[str], backend: Optional[str] = None) -> Transcripcion:
    backend = backend or cfg.stt_backend
    if backend not in PROVEEDORES_STT:
        raise SystemExit(f"Transcriptor desconocido: {backend}. Opciones: {', '.join(PROVEEDORES_STT)}")
    return PROVEEDORES_STT[backend](ruta, vocabulario)
