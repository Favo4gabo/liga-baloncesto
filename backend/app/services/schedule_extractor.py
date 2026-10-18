"""Extracción de horarios Excel/CSV/imagen con sugerencias de catálogo."""

import io
import re
import unicodedata
from datetime import date, datetime, time
from difflib import SequenceMatcher

import pandas as pd

from ..models import Arbitro, Ciudad, UbicacionCancha
from .vision import extraer_filas_imagen


ALIAS = {
    "fecha": ("fecha", "date", "dia", "día"),
    "hora": ("hora", "time", "horario"),
    "fecha_hora": ("fecha_hora", "fecha y hora", "fecha hora", "datetime", "inicio"),
    "arbitro": ("arbitro", "árbitro", "colegiado", "referee", "juez"),
    "cancha": ("cancha", "estadio", "sede", "venue", "pabellon"),
    "ciudad": ("ciudad", "localidad", "city", "municipio"),
}


def _limpiar_texto(valor) -> str:
    if valor is None or pd.isna(valor):
        return ""
    return str(valor).strip()


def _clave(valor: str) -> str:
    texto = unicodedata.normalize("NFKD", str(valor).lower())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r"[^a-z0-9]+", "", texto)


def _columna(columnas, tipo):
    alias = {_clave(item) for item in ALIAS[tipo]}
    for columna in columnas:
        if _clave(columna) in alias:
            return columna
    for columna in columnas:
        normalizada = _clave(columna)
        if any(item and (item in normalizada or normalizada in item) for item in alias if len(item) > 3):
            return columna
    return None


def _fecha_hora(fecha_valor, hora_valor="") -> tuple[str, str]:
    if isinstance(fecha_valor, (datetime, pd.Timestamp)):
        fecha_dt = pd.Timestamp(fecha_valor)
    elif isinstance(fecha_valor, date):
        fecha_dt = pd.Timestamp(fecha_valor)
    else:
        fecha_txt = _limpiar_texto(fecha_valor)
        formato_iso = bool(re.match(r"^\d{4}-\d{2}-\d{2}(?:[T ].*)?$", fecha_txt))
        fecha_dt = pd.to_datetime(fecha_txt, dayfirst=not formato_iso, errors="coerce") if fecha_txt else pd.NaT
    if pd.isna(fecha_dt):
        return "", _normalizar_hora(hora_valor)

    hora_txt = _normalizar_hora(hora_valor)
    if not hora_txt and isinstance(fecha_dt, pd.Timestamp) and (fecha_dt.hour or fecha_dt.minute):
        hora_txt = fecha_dt.strftime("%H:%M")
    return fecha_dt.strftime("%Y-%m-%d"), hora_txt


def _normalizar_hora(valor) -> str:
    if isinstance(valor, (datetime, pd.Timestamp, time)):
        return valor.strftime("%H:%M")
    texto = _limpiar_texto(valor)
    if not texto:
        return ""
    if isinstance(valor, (int, float)) and 0 <= valor < 1:
        minutos = round(float(valor) * 24 * 60)
        return f"{minutos // 60:02d}:{minutos % 60:02d}"
    try:
        convertido = pd.to_datetime(texto, errors="coerce")
        if not pd.isna(convertido):
            return convertido.strftime("%H:%M")
    except (TypeError, ValueError):
        pass
    match = re.search(r"\b(\d{1,2})[:h](\d{2})\b", texto.lower())
    if match and int(match.group(1)) < 24 and int(match.group(2)) < 60:
        return f"{int(match.group(1)):02d}:{int(match.group(2)):02d}"
    return ""


def _leer_tabular(contenido: bytes, extension: str):
    try:
        if extension == ".xlsx":
            return pd.read_excel(io.BytesIO(contenido), dtype=object).fillna("")
        return pd.read_csv(io.BytesIO(contenido), sep=None, engine="python", dtype=object).fillna("")
    except Exception as error:
        raise ValueError(f"No se pudo leer el archivo tabular: {error}") from error


def _mejor_coincidencia(texto: str, opciones, etiqueta) -> tuple[int | None, float]:
    consulta = _clave(texto)
    if not consulta:
        return None, 0.0
    mejor_id, mejor_score = None, 0.0
    for opcion in opciones:
        candidato = _clave(etiqueta(opcion))
        score = SequenceMatcher(None, consulta, candidato).ratio() if candidato else 0
        if consulta == candidato:
            score = 1.0
        elif consulta in candidato or candidato in consulta:
            score = max(score, 0.82)
        if score > mejor_score:
            mejor_id, mejor_score = opcion.id, score
    return (mejor_id if mejor_score >= 0.48 else None), round(mejor_score, 3)


def _resolver_sugerencias(fila: dict, arbitros, canchas, ciudades) -> dict:
    arbitro_id, score_arbitro = _mejor_coincidencia(
        fila["arbitro_texto"], arbitros, lambda item: f"{item.nombre} {item.apellido}"
    )
    cancha_id, score_cancha = _mejor_coincidencia(
        fila["cancha_texto"], canchas, lambda item: item.nombre_cancha
    )
    ciudad_id, score_ciudad = _mejor_coincidencia(
        fila["ciudad_texto"], ciudades, lambda item: item.nombre
    )
    cancha = next((item for item in canchas if item.id == cancha_id), None)
    if ciudad_id is None and cancha:
        ciudad_id = cancha.ciudad_id
        score_ciudad = 0.85
    scores = {
        "fecha": 1.0 if fila["fecha"] else 0.0,
        "hora": 1.0 if fila["hora"] else 0.0,
        "arbitro": score_arbitro,
        "cancha": score_cancha,
        "ciudad": score_ciudad,
    }
    return {
        **fila,
        "arbitro_id": arbitro_id,
        "cancha_id": cancha_id,
        "ciudad_id": ciudad_id,
        "confianza_campos": scores,
        "confianza": round(sum(scores.values()) / len(scores), 3),
    }


def _normalizar_filas_tabulares(frame) -> list[dict]:
    columnas = list(frame.columns)
    mapa = {tipo: _columna(columnas, tipo) for tipo in ALIAS}
    if not mapa["fecha"] and not mapa["fecha_hora"]:
        raise ValueError("El archivo debe incluir una columna de fecha o fecha/hora.")
    if not mapa["cancha"]:
        raise ValueError("El archivo debe incluir una columna de cancha, estadio o sede.")

    filas = []
    for indice, registro in frame.iterrows():
        fecha_valor = registro.get(mapa["fecha_hora"]) if mapa["fecha_hora"] else registro.get(mapa["fecha"])
        hora_valor = registro.get(mapa["hora"]) if mapa["hora"] else ""
        fecha, hora = _fecha_hora(fecha_valor, hora_valor)
        fila = {
            "fila_origen": int(indice) + 2,
            "fecha": fecha,
            "hora": hora,
            "arbitro_texto": _limpiar_texto(registro.get(mapa["arbitro"])) if mapa["arbitro"] else "",
            "cancha_texto": _limpiar_texto(registro.get(mapa["cancha"])) if mapa["cancha"] else "",
            "ciudad_texto": _limpiar_texto(registro.get(mapa["ciudad"])) if mapa["ciudad"] else "",
        }
        if not any(fila[campo] for campo in ("fecha", "hora", "arbitro_texto", "cancha_texto", "ciudad_texto")):
            continue
        filas.append(fila)
    return filas


def extraer_horario_arbitro(archivo_o_imagen, filename: str | None = None) -> dict:
    """Extrae filas sin escribir datos en la base; devuelve IDs sugeridos."""
    if hasattr(archivo_o_imagen, "read"):
        archivo = archivo_o_imagen
        filename = filename or getattr(archivo, "filename", "")
        contenido = archivo.read()
    else:
        contenido = archivo_o_imagen
    if not isinstance(contenido, (bytes, bytearray)):
        raise ValueError("El archivo debe recibirse como bytes o como archivo abierto.")
    extension = (filename or "").lower().rsplit(".", 1)[-1]
    extension = f".{extension}" if extension else ""
    advertencias, proveedor, modelo = [], "tabular", None

    if extension in {".xlsx", ".csv"}:
        origen = _normalizar_filas_tabulares(_leer_tabular(bytes(contenido), extension))
    elif extension in {".png", ".jpg", ".jpeg"}:
        mime_type = "image/png" if extension == ".png" else "image/jpeg"
        resultado = extraer_filas_imagen(bytes(contenido), filename or "horario", mime_type)
        proveedor, modelo = resultado["proveedor"], resultado.get("modelo")
        advertencias.extend(resultado.get("advertencias", []))
        origen = []
        for indice, item in enumerate(resultado["filas"], start=1):
            if not isinstance(item, dict):
                continue
            fecha, hora = _fecha_hora(item.get("fecha") or item.get("fecha_hora"), item.get("hora"))
            origen.append({
                "fila_origen": indice,
                "fecha": fecha,
                "hora": hora,
                "arbitro_texto": _limpiar_texto(item.get("arbitro") or item.get("referee")),
                "cancha_texto": _limpiar_texto(item.get("cancha") or item.get("estadio") or item.get("venue")),
                "ciudad_texto": _limpiar_texto(item.get("ciudad") or item.get("city")),
                "_confianza_origen": item.get("confianza", 0.7),
            })
    else:
        raise ValueError("Formato no permitido. Adjunta un .xlsx, .csv, .png, .jpg o .jpeg.")

    if not origen:
        raise ValueError("No se encontraron filas de horario para previsualizar.")
    arbitros = Arbitro.query.filter_by(activo=True).all()
    canchas = UbicacionCancha.query.all()
    ciudades = Ciudad.query.all()
    filas = []
    for item in origen:
        origen_confianza = item.pop("_confianza_origen", None)
        fila = _resolver_sugerencias(item, arbitros, canchas, ciudades)
        if origen_confianza is not None:
            try:
                confianza_origen = max(0.0, min(1.0, float(origen_confianza)))
            except (TypeError, ValueError):
                confianza_origen = 0.5
            fila["confianza"] = min(fila["confianza"], confianza_origen)
            fila["confianza_campos"] = {
                campo: min(score, confianza_origen)
                for campo, score in fila["confianza_campos"].items()
            }
        filas.append(fila)
    return {
        "solo_lectura": True,
        "origen": proveedor,
        "modelo": modelo,
        "advertencias": advertencias,
        "filas": filas,
    }
