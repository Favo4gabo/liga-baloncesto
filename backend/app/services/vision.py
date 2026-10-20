"""Adaptadores de visión multimodal para horarios deportivos."""

import base64
import json
import os
import re
import time


PROMPT_SISTEMA = """
Eres un extractor de datos para calendarios y logística de árbitros de baloncesto.
Sigue el esquema JSON incluido en el mensaje del usuario y devuelve exclusivamente
un objeto JSON válido. Una fila representa una asignación única (un árbitro × un
partido), nunca combines varios árbitros en una misma fila.

Reglas de lectura y relación:
- Relaciona fecha, hora, cancha, ciudad de destino, árbitro y logística usando la
  misma fila, bloque o intersección de matriz. En matrices de fechas × árbitros,
  genera una fila por cada celda que indique una asignación; no generes el producto
  cartesiano si la hoja no marca todas esas intersecciones.
- Si una celda contiene varios árbitros, sepáralos y genera una fila por árbitro.
- Interpreta nombres como «Apellido, Nombre» como una sola persona; normaliza la
  salida a «Nombre Apellido» sin perder apellidos compuestos.
- Interpreta fechas dd/mm/yyyy (y dd/mm cuando el año sea explícito en el libro);
  entrega YYYY-MM-DD. Si el año no se puede determinar, deja la fecha vacía.
- Interpreta horas en formato de 24 horas y entrega HH:MM. No inventes AM/PM.
- ciudad_origen corresponde al origen del árbitro; ciudad_destino a la ciudad del
  partido. Usa tablas de catálogo solo cuando la relación sea explícita y segura.
- medio_transporte solo puede ser avion, terrestre o null. No lo deduzcas por la
  distancia, las ciudades, el costo ni el medio habitual del árbitro: debe estar
  indicado explícitamente.
- Si hay una columna explícita HOSPEDAJE, conserva su importe como hospedaje_total
  de toda la asignación (no como tarifa por noche). Si no aparece, usa null.
- No inventes datos ni completes valores por intuición. Usa cadena vacía o null
  según el esquema, reduce confianza y explica la incertidumbre en notas.
- evidencia debe identificar hoja/tabla y número de fila (o ubicación visual en
  la imagen); no afirmes una fila de origen que no puedas ubicar.
- confianza es un número entre 0 y 1 que refleja legibilidad y seguridad de las
  asociaciones, no solo la calidad de lectura OCR.
""".strip()

# Alias temporal para mantener compatibilidad con consumidores previos.
PROMPT_HORARIO = PROMPT_SISTEMA

PROVEEDORES_SIMULADOS = {"simulado", "emulado", "local"}

HORARIO_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["filas", "advertencias"],
    "properties": {
        "filas": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["fecha", "hora", "arbitro", "ciudad_origen", "ciudad_destino", "cancha", "medio_transporte", "cantidad_dias", "cantidad_noches", "viatico_por_dia", "hospedaje_total", "evidencia", "confianza", "notas", "presupuesto"],
                "properties": {
                    "fecha": {"type": "string"}, "hora": {"type": "string"},
                    "arbitro": {"type": "string"}, "ciudad_origen": {"type": "string"},
                    "ciudad_destino": {"type": "string"}, "cancha": {"type": "string"},
                    "medio_transporte": {"type": ["string", "null"], "enum": ["avion", "terrestre", None]},
                    "cantidad_dias": {"type": ["integer", "null"]},
                    "cantidad_noches": {"type": ["integer", "null"]},
                    "viatico_por_dia": {"type": ["number", "null"]},
                    "hospedaje_total": {"type": ["number", "null"]},
                    "presupuesto": {"type": ["number", "null"]},
                    "evidencia": {"type": "string"},
                    "confianza": {"type": "number", "minimum": 0, "maximum": 1},
                    "notas": {"type": "string"},
                },
            },
        },
        "advertencias": {"type": "array", "items": {"type": "string"}},
    },
}

CATALOGOS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["estados_ciudades", "tarifas_traslado", "tarifas_hospedaje", "estados_cercanos", "arbitros", "advertencias"],
    "properties": {
        "estados_ciudades": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["estado", "ciudad"], "properties": {"estado": {"type": "string"}, "ciudad": {"type": "string"}}}},
        "tarifas_traslado": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["tipo", "costo_base"], "properties": {"tipo": {"type": "string"}, "costo_base": {"type": ["number", "null"]}}}},
        "tarifas_hospedaje": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["ciudad", "costo_noche", "viatico_por_dia"], "properties": {"ciudad": {"type": "string"}, "costo_noche": {"type": ["number", "null"]}, "viatico_por_dia": {"type": ["number", "null"]}}}},
        "estados_cercanos": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["estado_a", "estado_b"], "properties": {"estado_a": {"type": "string"}, "estado_b": {"type": "string"}}}},
        "arbitros": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["nombre", "apellido", "telefono", "email", "ciudad_origen"], "properties": {"nombre": {"type": "string"}, "apellido": {"type": "string"}, "telefono": {"type": ["string", "null"]}, "email": {"type": ["string", "null"]}, "ciudad_origen": {"type": "string"}}}},
        "advertencias": {"type": "array", "items": {"type": "string"}},
    },
}


def _detalle_proveedor(error) -> str:
    detalle = getattr(getattr(error, "response", None), "text", "") or str(error)
    if "401" in detalle or "User not found" in detalle:
        return "la credencial de OpenRouter no es válida o fue revocada"
    return detalle[:300]


def _json_objeto(texto: str) -> dict:
    texto = texto.strip()
    bloque = re.search(r"`{1,3}(?:json)?\s*(.*?)`{1,3}", texto, flags=re.IGNORECASE | re.DOTALL)
    if bloque:
        texto = bloque.group(1).strip()
    try:
        resultado = json.loads(texto)
    except json.JSONDecodeError as error:
        inicio = texto.find("{")
        if inicio < 0:
            raise ValueError("El proveedor de visión no devolvió un JSON válido.") from error
        try:
            resultado, _ = json.JSONDecoder().raw_decode(texto[inicio:])
        except json.JSONDecodeError as nested_error:
            raise ValueError("El proveedor de visión no devolvió un JSON válido.") from nested_error
    if not isinstance(resultado, dict):
        raise ValueError("La respuesta del proveedor no contiene un objeto JSON.")
    return resultado


def _respuesta_json(texto: str) -> dict:
    resultado = _json_objeto(texto)
    if not isinstance(resultado.get("filas"), list):
        raise ValueError("La respuesta de visión debe contener una lista 'filas'.")
    return resultado


def _cliente_http():
    """Importación diferida: el modo simulado funciona sin instalar requests."""
    try:
        import requests
    except ImportError as error:
        raise ValueError("Falta la dependencia requests. Instala backend/requirements.txt.") from error
    return requests


def _clave_openrouter() -> str:
    """Credencial dedicada a migraciones si existe; si no, la habitual."""
    api_key = (os.getenv("MIGRATION_AI_API_KEY") or "").strip()
    api_key = api_key or (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not api_key:
        raise ValueError(
            "Falta MIGRATION_AI_API_KEY u OPENROUTER_API_KEY para procesar con OpenRouter."
        )
    return api_key


def _configuracion_openrouter(vision: bool = False) -> tuple[str, str]:
    """Devuelve (clave, modelo).

    La lectura de imágenes usa el modelo multimodal (`OPENROUTER_MODEL`); la
    normalización de texto de Excel/CSV admite un modelo distinto
    (`MIGRATION_AI_MODEL`), útil cuando este último no procesa imágenes.
    """
    api_key = _clave_openrouter()
    if vision:
        modelo = (os.getenv("OPENROUTER_MODEL") or "").strip()
    else:
        modelo = (os.getenv("MIGRATION_AI_MODEL") or "").strip()
        modelo = modelo or (os.getenv("OPENROUTER_MODEL") or "").strip()
    return api_key, modelo or "google/gemini-3.8-flash"


def _modelos_fallback(modelo: str) -> list[str]:
    configurados = os.getenv("OPENROUTER_FALLBACK_MODELS", "")
    try:
        parsed = json.loads(configurados) if configurados.strip().startswith("[") else None
    except json.JSONDecodeError:
        parsed = None
    alternativos = parsed if isinstance(parsed, list) else configurados.split(",")
    return list(dict.fromkeys([modelo, *(str(item).strip() for item in alternativos if str(item).strip() and str(item).strip() != modelo)]))


def _llamar_openrouter(messages, vision, schema):
    """Invoca OpenRouter con salida JSON estricta, fallback y reintentos acotados."""
    api_key, modelo = _configuracion_openrouter(vision=vision)
    requests = _cliente_http()
    try:
        timeout_read = float(os.getenv("LLM_TIMEOUT_READ", "90"))
    except ValueError:
        timeout_read = 90.0
    timeout_read = max(1.0, timeout_read)
    payload = {
        "model": modelo,
        "models": _modelos_fallback(modelo),
        "temperature": 0,
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "arbiliga_response", "strict": True, "schema": schema},
        },
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173"),
        "X-Title": "ArbiLiga Schedule Reader",
    }
    ultima_respuesta = None
    # Tres reintentos (cuatro intentos totales), solo para limitación o fallos transitorios.
    for intento in range(4):
        try:
            respuesta = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=(10, timeout_read),
            )
            status = getattr(respuesta, "status_code", 200)
            if status in {429, 502, 503} and intento < 3:
                time.sleep(0.5 * (2 ** intento))
                continue
            respuesta.raise_for_status()
            cuerpo = respuesta.json()
            contenido = cuerpo["choices"][0]["message"]["content"]
            modelo_usado = cuerpo.get("model") or modelo
            return contenido, modelo_usado
        except requests.Timeout as error:
            raise ValueError("OpenRouter tardó demasiado en procesar el archivo.") from error
        except requests.RequestException as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            if status in {429, 502, 503} and intento < 3:
                ultima_respuesta = error
                time.sleep(0.5 * (2 ** intento))
                continue
            raise ValueError(f"No se pudo consultar OpenRouter: {_detalle_proveedor(error)}") from error
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("OpenRouter devolvió una respuesta sin contenido reconocible.") from error
    raise ValueError(f"OpenRouter no respondió tras reintentos: {_detalle_proveedor(ultima_respuesta)}")


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


def _texto_catalogo(catalogo) -> str:
    if not catalogo:
        return ""
    return "\n\nCATÁLOGO CANÓNICO (referencia; no inventes coincidencias):\n" + json.dumps(catalogo, ensure_ascii=False)


def _openrouter(contenido: bytes, mime_type: str, catalogo=None) -> dict:
    data_url = f"data:{mime_type};base64,{base64.b64encode(contenido).decode('ascii')}"
    mensajes = [
        {"role": "system", "content": PROMPT_SISTEMA},
        {"role": "user", "content": [
            {"type": "text", "text": "Extrae el horario de esta imagen y responde con el esquema solicitado." + _texto_catalogo(catalogo)},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]},
    ]
    contenido_respuesta, modelo = _llamar_openrouter(mensajes, vision=True, schema=HORARIO_SCHEMA)
    resultado = _respuesta_json(_texto_partes(contenido_respuesta))
    return {
        "proveedor": "openrouter",
        "modelo": modelo,
        "filas": resultado["filas"],
        "advertencias": resultado.get("advertencias", []),
    }


def _gemini(contenido: bytes, mime_type: str, catalogo=None) -> dict:
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
                {"text": PROMPT_SISTEMA + _texto_catalogo(catalogo)},
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


def extraer_filas_excel_texto(texto_libro: str | list[str], catalogo=None) -> dict:
    """Pide a la IA interpretar el contenido textual de todas las hojas Excel."""
    proveedor = os.getenv("VISION_PROVIDER", "simulado").strip().lower()
    if proveedor in PROVEEDORES_SIMULADOS:
        raise ValueError("La IA está en modo simulado; se usará la detección local del Excel.")

    fragmentos = texto_libro if isinstance(texto_libro, list) else [texto_libro]
    if not fragmentos:
        raise ValueError("El archivo no contiene texto tabular para interpretar.")
    requests = _cliente_http()
    filas, advertencias, modelos = [], [], []
    for indice, fragmento in enumerate(fragmentos, start=1):
        prompt = f"""
Extrae las asignaciones de horario de este fragmento tabular. Puede ser parte de
una hoja o tabla apilada. Devuelve una fila por árbitro y partido conforme al
esquema JSON estricto. Si no hay asignaciones, devuelve filas vacías; no inventes
contenido faltante de otros fragmentos.

FRAGMENTO {indice}/{len(fragmentos)}:
{fragmento}
{_texto_catalogo(catalogo)}
""".strip()
        try:
            if proveedor == "openrouter":
                contenido, modelo = _llamar_openrouter(
                    [{"role": "system", "content": PROMPT_SISTEMA}, {"role": "user", "content": prompt}],
                    vision=False,
                    schema=HORARIO_SCHEMA,
                )
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
                        "contents": [{"role": "user", "parts": [{"text": f"{PROMPT_SISTEMA}\n\n{prompt}"}]}],
                        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
                    },
                    timeout=(10, float(os.getenv("LLM_TIMEOUT_READ", "90"))),
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
        filas.extend(resultado["filas"])
        advertencias.extend(resultado.get("advertencias", []))
        if modelo:
            modelos.append(modelo)
    return {
        "proveedor": proveedor,
        "modelo": ", ".join(dict.fromkeys(modelos)) if modelos else None,
        "filas": filas,
        "advertencias": advertencias,
    }


def extraer_catalogos_excel(texto_libro: str) -> dict:
    """Interpreta bloques de catálogo no estándar como fallback del parser local.

    Se usa únicamente cuando el Excel parece contener un bloque de árbitros pero
    sus encabezados no pudieron mapearse con los alias conocidos.
    """
    proveedor = os.getenv("VISION_PROVIDER", "simulado").strip().lower()
    if proveedor in PROVEEDORES_SIMULADOS:
        raise ValueError("La IA está en modo simulado; no se analizaron los bloques del catálogo.")

    esquema = {
        "estados_ciudades": [{"estado": "", "ciudad": ""}],
        "tarifas_traslado": [{"tipo": "", "costo_base": None}],
        "tarifas_hospedaje": [{"ciudad": "", "costo_noche": None, "viatico_por_dia": None}],
        "estados_cercanos": [{"estado_a": "", "estado_b": ""}],
        "arbitros": [{"nombre": "", "apellido": "", "telefono": None, "email": None, "ciudad_origen": ""}],
        "advertencias": [],
    }
    prompt = f"""
Interpreta las tablas de catálogo de este libro de una liga de baloncesto. Las
tablas pueden estar apiladas en una sola hoja, separadas por filas vacías, con
títulos y encabezados variados. Devuelve solo JSON con las claves y la estructura
indicadas. Omite tablas ausentes y filas de encabezado/título. No inventes valores;
si un campo no se lee, usa null. Mantén nombres y teléfonos exactamente como aparecen.
Para tarifas, conserva el texto original de tipo. Los viáticos del libro deben
extraerse como viatico_por_dia; no confundas viáticos con costo de hotel.

ESQUEMA:
{json.dumps(esquema, ensure_ascii=False)}

CONTENIDO DEL LIBRO:
{texto_libro[:60000]}
""".strip()
    requests = _cliente_http()
    try:
        if proveedor == "openrouter":
            contenido, modelo = _llamar_openrouter(
            [{"role": "system", "content": PROMPT_SISTEMA}, {"role": "user", "content": prompt}],
                vision=False,
                schema=CATALOGOS_SCHEMA,
            )
        elif proveedor in {"gemini", "google"}:
            api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
            if not api_key:
                raise ValueError("Falta GEMINI_API_KEY para interpretar los catálogos.")
            modelo = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            respuesta = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"role": "user", "parts": [{"text": f"{PROMPT_SISTEMA}\n\n{prompt}"}]}],
                    "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
                },
                timeout=(10, 90),
            )
            respuesta.raise_for_status()
            contenido = respuesta.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            raise ValueError("VISION_PROVIDER debe ser 'openrouter', 'gemini' o 'simulado'.")
    except requests.Timeout as error:
        raise ValueError(f"{proveedor} tardó demasiado en analizar los catálogos.") from error
    except requests.RequestException as error:
        raise ValueError(f"No se pudieron interpretar los catálogos con {proveedor}: {_detalle_proveedor(error)}") from error
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError(f"{proveedor} devolvió una respuesta sin contenido reconocible.") from error

    resultado = _json_objeto(_texto_partes(contenido))
    listas = ("estados_ciudades", "tarifas_traslado", "tarifas_hospedaje", "estados_cercanos", "arbitros")
    for clave in listas:
        if clave in resultado and not isinstance(resultado[clave], list):
            raise ValueError(f"La respuesta de IA tiene un formato inválido en '{clave}'.")
    return {"proveedor": proveedor, "modelo": modelo, **resultado}


def extraer_filas_imagen(contenido: bytes, filename: str, mime_type: str, catalogo=None) -> dict:
    """Obtiene filas de la imagen con OpenRouter, la API de Gemini o el modo simulado."""
    proveedor = os.getenv("VISION_PROVIDER", "simulado").strip().lower()
    if proveedor in PROVEEDORES_SIMULADOS:
        return _modo_simulado()
    if proveedor == "openrouter":
        return _openrouter(contenido, mime_type, catalogo=catalogo)
    if proveedor in {"gemini", "google"}:
        return _gemini(contenido, mime_type, catalogo=catalogo)
    raise ValueError("VISION_PROVIDER debe ser 'openrouter', 'gemini' o 'simulado'.")
