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

PROVEEDORES_SIMULADOS = {"simulado", "emulado", "local"}


def _detalle_proveedor(error) -> str:
    detalle = getattr(getattr(error, "response", None), "text", "") or str(error)
    if "401" in detalle or "User not found" in detalle:
        return "la credencial de OpenRouter no es válida o fue revocada"
    return detalle[:300]


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


def _cliente_http():
    """Importación diferida: el modo simulado funciona sin instalar requests."""
    try:
        import requests
    except ImportError as error:
        raise ValueError("Falta la dependencia requests. Instala backend/requirements.txt.") from error
    return requests


def _modo_simulado() -> dict:
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
            "Modo simulado: no se procesó la imagen. Configura VISION_PROVIDER=openrouter "
            "o VISION_PROVIDER=gemini para usar visión real."
        ],
    }


def _texto_partes(contenido) -> str:
    if isinstance(contenido, list):
        return "\n".join(
            parte.get("text", "") for parte in contenido if isinstance(parte, dict)
        )
    return str(contenido)


def _openrouter(contenido: bytes, mime_type: str) -> dict:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Falta OPENROUTER_API_KEY para procesar imágenes con visión.")
    requests = _cliente_http()

    data_url = f"data:{mime_type};base64,{base64.b64encode(contenido).decode('ascii')}"
    modelo = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    payload = {
        "model": modelo,
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
        raise ValueError(f"No se pudo consultar OpenRouter: {_detalle_proveedor(error)}") from error
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("OpenRouter devolvió una respuesta sin contenido reconocible.") from error

    resultado = _respuesta_json(_texto_partes(contenido_respuesta))
    return {
        "proveedor": "openrouter",
        "modelo": modelo,
        "filas": resultado["filas"],
        "advertencias": resultado.get("advertencias", []),
    }


def _gemini(contenido: bytes, mime_type: str) -> dict:
    """Usa la API de Google (Google AI Studio) de forma directa, sin OpenRouter."""
    api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("Falta GEMINI_API_KEY para procesar imágenes con la API de Google.")
    requests = _cliente_http()

    modelo = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    payload = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": PROMPT_HORARIO},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(contenido).decode("ascii"),
                    }
                },
            ],
        }],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    try:
        respuesta = requests.post(
            url,
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json=payload,
            timeout=(10, 90),
        )
        respuesta.raise_for_status()
        candidatos = respuesta.json()["candidates"]
        partes = candidatos[0]["content"]["parts"]
    except requests.Timeout as error:
        raise ValueError("Gemini tardó demasiado en procesar la imagen.") from error
    except requests.RequestException as error:
        raise ValueError(f"No se pudo consultar Gemini: {_detalle_proveedor(error)}") from error
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Gemini devolvió una respuesta sin contenido reconocible.") from error

    resultado = _respuesta_json(_texto_partes(partes))
    return {
        "proveedor": "gemini",
        "modelo": modelo,
        "filas": resultado["filas"],
        "advertencias": resultado.get("advertencias", []),
    }


def extraer_filas_excel_texto(texto_libro: str) -> dict:
    """Pide a la IA interpretar el contenido textual de todas las hojas Excel."""
    proveedor = os.getenv("VISION_PROVIDER", "simulado").strip().lower()
    if proveedor in PROVEEDORES_SIMULADOS:
        raise ValueError("La IA está en modo simulado; se usará la detección local del Excel.")

    prompt = f"""
Analiza el contenido completo de este libro de Excel. Puede tener varias hojas o
varias tablas separadas en una misma hoja, con títulos, filas vacías y nombres de
columnas no estandarizados. Identifica las filas de partidos/horarios y usa las
otras tablas (árbitros, ciudades, sedes, tarifas y viáticos) únicamente para
completar datos relacionados cuando la asociación sea clara. No inventes datos.
No confundas presupuestos o tarifas de catálogo con el presupuesto de un partido.
Devuelve exclusivamente JSON con esta forma:
{{"filas":[{{"fecha":"YYYY-MM-DD o vacío","hora":"HH:MM o vacío",
"arbitro":"nombre completo o vacío","cancha":"sede/estadio o vacío",
"ciudad":"ciudad sede o vacío","cantidad_dias":1,"cantidad_noches":1,
"viatico_por_dia":null,"presupuesto":null,"confianza":0.0,
"notas":"ambigüedad importante o vacío"}}]}}.
Si un partido tiene más de un árbitro explícito, devuelve una fila por árbitro.
Si una asociación no es segura, deja el campo vacío y explica la duda en notas.

CONTENIDO COMPLETO DEL LIBRO (todas las hojas y celdas no vacías):
{texto_libro}
""".strip()
    requests = _cliente_http()

    try:
        if proveedor == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not api_key:
                raise ValueError("Falta OPENROUTER_API_KEY para interpretar el Excel con IA.")
            modelo = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash")
            respuesta = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
                    "X-Title": "ArbiLiga Schedule Reader",
                },
                json={
                    "model": modelo,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=(10, 90),
            )
            respuesta.raise_for_status()
            contenido = respuesta.json()["choices"][0]["message"]["content"]
        elif proveedor in {"gemini", "google"}:
            api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
            if not api_key:
                raise ValueError("Falta GEMINI_API_KEY para interpretar el Excel con Gemini.")
            modelo = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
            respuesta = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
                },
                timeout=(10, 90),
            )
            respuesta.raise_for_status()
            contenido = respuesta.json()["candidates"][0]["content"]["parts"]
        else:
            raise ValueError("VISION_PROVIDER debe ser 'openrouter', 'gemini' o 'simulado'.")
    except requests.Timeout as error:
        raise ValueError(f"{proveedor} tardó demasiado en interpretar el Excel.") from error
    except requests.RequestException as error:
        raise ValueError(f"No se pudo consultar {proveedor}: {_detalle_proveedor(error)}") from error
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"{proveedor} devolvió una respuesta sin contenido reconocible.") from error

    resultado = _respuesta_json(_texto_partes(contenido))
    return {
        "proveedor": proveedor,
        "modelo": modelo,
        "filas": resultado["filas"],
        "advertencias": resultado.get("advertencias", []),
    }


def extraer_filas_imagen(contenido: bytes, filename: str, mime_type: str) -> dict:
    """Obtiene filas de la imagen con OpenRouter, la API de Gemini o el modo simulado."""
    proveedor = os.getenv("VISION_PROVIDER", "simulado").strip().lower()
    if proveedor in PROVEEDORES_SIMULADOS:
        return _modo_simulado()
    if proveedor == "openrouter":
        return _openrouter(contenido, mime_type)
    if proveedor in {"gemini", "google"}:
        return _gemini(contenido, mime_type)
    raise ValueError("VISION_PROVIDER debe ser 'openrouter', 'gemini' o 'simulado'.")
