"""Adaptadores de visión multimodal para horarios deportivos."""

import base64
import json
import os
import re


PROMPT_HORARIO = """
Lee la imagen de un horario de baloncesto y extrae una fila por cada partido o
asignación arbitral. Responde exclusivamente JSON con esta forma:
{"filas":[{"fecha":"YYYY-MM-DD","hora":"HH:MM","arbitro":"nombre completo o vacío",
"cancha":"nombre de cancha/estadio o vacío","ciudad":"ciudad o vacío",
"confianza":0.0}]}.
No inventes datos. Si un dato no es legible, usa cadena vacía y reduce confianza.
Si aparecen dos árbitros para el mismo partido, devuelve una fila por árbitro.
""".strip()


def _respuesta_json(texto: str) -> dict:
    texto = texto.strip()
    bloque = re.search(r"```(?:json)?\s*(.*?)```", texto, flags=re.IGNORECASE | re.DOTALL)
    if bloque:
        texto = bloque.group(1).strip()
    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError as error:
        raise ValueError("El proveedor de visión no devolvió un JSON válido.") from error
    if not isinstance(resultado, dict) or not isinstance(resultado.get("filas"), list):
        raise ValueError("La respuesta de visión debe contener una lista 'filas'.")
    return resultado


def extraer_filas_imagen(contenido: bytes, filename: str, mime_type: str) -> dict:
    """Obtiene filas de la imagen usando OpenRouter o el adaptador simulado local."""
    proveedor = os.getenv("VISION_PROVIDER", "simulado").strip().lower()
    if proveedor in {"simulado", "emulado", "local"}:
        return {
            "proveedor": "simulado",
            "modelo": "local-demo",
            "filas": [{
                "fecha": "",
                "hora": "",
                "arbitro": "",
                "cancha": "",
                "ciudad": "",
                "confianza": 0.0,
            }],
            "advertencias": [
                "Modo simulado: no se procesó la imagen. Configura VISION_PROVIDER=openrouter para usar visión real."
            ],
        }

    if proveedor != "openrouter":
        raise ValueError("VISION_PROVIDER debe ser 'openrouter' o 'simulado'.")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Falta OPENROUTER_API_KEY para procesar imágenes con visión.")

    # Importación diferida para que el modo simulado funcione sin instalar o
    # cargar el cliente HTTP durante el desarrollo sin conexión.
    try:
        import requests
    except ImportError as error:
        raise ValueError("Falta la dependencia requests. Instala backend/requirements.txt.") from error

    data_url = f"data:{mime_type};base64,{base64.b64encode(contenido).decode('ascii')}"
    payload = {
        "model": os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash"),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT_HORARIO},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }],
    }
    try:
        respuesta = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
                "X-Title": "ArbiLiga Schedule Reader",
            },
            json=payload,
            timeout=(10, 90),
        )
        respuesta.raise_for_status()
        contenido_respuesta = respuesta.json()["choices"][0]["message"]["content"]
    except requests.Timeout as error:
        raise ValueError("OpenRouter tardó demasiado en procesar la imagen.") from error
    except requests.RequestException as error:
        detalle = getattr(getattr(error, "response", None), "text", "")
        raise ValueError(f"No se pudo consultar OpenRouter: {detalle[:300] or str(error)}") from error
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("OpenRouter devolvió una respuesta sin contenido reconocible.") from error

    if isinstance(contenido_respuesta, list):
        contenido_respuesta = "\n".join(
            parte.get("text", "") for parte in contenido_respuesta if isinstance(parte, dict)
        )
    resultado = _respuesta_json(str(contenido_respuesta))
    return {
        "proveedor": "openrouter",
        "modelo": payload["model"],
        "filas": resultado["filas"],
        "advertencias": resultado.get("advertencias", []),
    }
