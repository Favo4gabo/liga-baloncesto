"""Extracción de horarios Excel/CSV/imagen con sugerencias de catálogo."""

import io
import os
import re
import unicodedata
from datetime import date, datetime, time
from difflib import SequenceMatcher

import pandas as pd

from ..models import Arbitro, Ciudad, UbicacionCancha
from .vision import extraer_filas_excel_texto, extraer_filas_imagen


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


def _texto_compacto(valor) -> str:
    """Normaliza saltos y espacios que suelen aparecer en celdas pegadas desde Excel."""
    return re.sub(r"\s+", " ", _limpiar_texto(valor))


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


def _normalizar_filas_excel(contenido: bytes) -> list[dict]:
    """Busca tablas de partidos en cualquier hoja y fila del libro.

    Muchos libros de liga agrupan varios catálogos en bloques de una sola hoja;
    por eso no se puede asumir que la fila 1 sea la cabecera del horario.
    """
    try:
        hojas = pd.read_excel(io.BytesIO(contenido), sheet_name=None, header=None, dtype=object)
    except Exception as error:
        raise ValueError(f"No se pudo leer el archivo Excel: {error}") from error

    filas = []
    for nombre_hoja, hoja in hojas.items():
        for indice_cabecera, serie in hoja.iterrows():
            valores = [_texto_compacto(valor) for valor in serie.tolist()]
            indices_columnas = [indice for indice, valor in enumerate(valores) if valor]
            columnas = [valores[indice] for indice in indices_columnas]
            mapa = {tipo: _columna(columnas, tipo) for tipo in ALIAS}
            if not (mapa["fecha"] or mapa["fecha_hora"]) or not mapa["cancha"]:
                continue

            registros = []
            for indice_fila in range(indice_cabecera + 1, len(hoja)):
                valores_fila = hoja.iloc[indice_fila].tolist()
                registro = {
                    columna: valores_fila[indice]
                    for indice, columna in zip(indices_columnas, columnas)
                    if indice < len(valores_fila)
                }
                # Los bloques del Excel de ejemplo están separados por una fila vacía.
                if not any(not _vacio_excel(valor) for valor in valores_fila):
                    if registros:
                        break
                    continue
                registros.append(registro)
            if registros:
                frame = pd.DataFrame(registros, columns=columnas)
                frame.index = range(indice_cabecera, indice_cabecera + len(frame))
                bloque = _normalizar_filas_tabulares(frame)
                for fila in bloque:
                    fila["hoja_origen"] = nombre_hoja
                    filas.append(fila)
                # No volver a interpretar como encabezado el contenido de este bloque.
                break
    if not filas:
        raise ValueError(
            "No encontré una tabla de partidos en el Excel. Se requiere una fila de encabezados "
            "con fecha, cancha/estadio y, si están disponibles, hora, árbitro y ciudad."
        )
    return filas


def _vacio_excel(valor) -> bool:
    return valor is None or pd.isna(valor) or (isinstance(valor, str) and not valor.strip())


def _texto_completo_excel(contenido: bytes) -> str:
    """Serializa todas las hojas para que la IA pueda asociar tablas del libro."""
    hojas = pd.read_excel(io.BytesIO(contenido), sheet_name=None, header=None, dtype=object)
    secciones = []
    for nombre, hoja in hojas.items():
        lineas = []
        for valores in hoja.itertuples(index=False, name=None):
            celdas = [f"{indice + 1}={_limpiar_texto(valor)}" for indice, valor in enumerate(valores) if not _vacio_excel(valor)]
            if celdas:
                lineas.append(" | ".join(celdas))
        secciones.append(f"HOJA: {nombre}\n" + "\n".join(lineas))
    return "\n\n".join(secciones)


def _filas_desde_ia(resultado: dict) -> list[dict]:
    filas = []
    for indice, item in enumerate(resultado.get("filas", []), start=1):
        if not isinstance(item, dict):
            continue
        fecha, hora = _fecha_hora(item.get("fecha") or item.get("fecha_hora"), item.get("hora"))
        fila = {
            "fila_origen": indice,
            "fecha": fecha,
            "hora": hora,
            "arbitro_texto": _limpiar_texto(item.get("arbitro") or item.get("referee")),
            "cancha_texto": _limpiar_texto(item.get("cancha") or item.get("estadio") or item.get("venue")),
            "ciudad_texto": _limpiar_texto(item.get("ciudad") or item.get("city")),
            "_confianza_origen": item.get("confianza", 0.65),
        }
        for campo in ("cantidad_dias", "cantidad_noches", "viatico_por_dia", "presupuesto", "notas"):
            if item.get(campo) is not None:
                fila[campo] = item[campo]
        filas.append(fila)
    return filas


def _mejor_coincidencia(texto: str, opciones, etiqueta) -> tuple[int | None, float]:
    consulta = _clave(texto)
    if not consulta:
        return None, 0.0

    # Algunos libros ya contienen los IDs internos en vez de los nombres.
    # Excel suele cargarlos como número entero o decimal terminado en .0.
    if re.fullmatch(r"[1-9]\d*(?:\.0+)?", str(texto).strip()):
        id_directo = int(float(texto))
        if any(opcion.id == id_directo for opcion in opciones):
            return id_directo, 1.0

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
            "arbitro_texto": _texto_compacto(registro.get(mapa["arbitro"])) if mapa["arbitro"] else "",
            "cancha_texto": _texto_compacto(registro.get(mapa["cancha"])) if mapa["cancha"] else "",
            "ciudad_texto": _texto_compacto(registro.get(mapa["ciudad"])) if mapa["ciudad"] else "",
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

    if extension == ".xlsx":
        error_ia = None
        if os.getenv("VISION_PROVIDER", "simulado").strip().lower() not in {"simulado", "emulado", "local"}:
            try:
                resultado_ia = extraer_filas_excel_texto(_texto_completo_excel(bytes(contenido)))
                origen = _filas_desde_ia(resultado_ia)
                proveedor, modelo = resultado_ia["proveedor"], resultado_ia.get("modelo")
                advertencias.extend(resultado_ia.get("advertencias", []))
                if not origen:
                    raise ValueError("La IA no identificó filas de partidos en el libro.")
            except ValueError as error:
                error_ia = error
                origen = []
        else:
            origen = []
        if not origen:
            try:
                origen = _normalizar_filas_excel(bytes(contenido))
                proveedor, modelo = "lectura local", None
                if error_ia:
                    advertencias.append(
                        f"No se pudo usar la IA ({error_ia}). Se aplicó la detección local por encabezados. "
                        "Revisa cuidadosamente los datos antes de confirmar."
                    )
            except ValueError as error_local:
                if error_ia:
                    raise ValueError(
                        f"La IA no pudo interpretar el libro ({error_ia}) y la lectura local tampoco encontró "
                        f"una tabla reconocible ({error_local}). Revisa el archivo o completa la plantilla manualmente."
                    ) from error_local
                raise
    elif extension == ".csv":
        error_ia = None
        if os.getenv("VISION_PROVIDER", "simulado").strip().lower() not in {"simulado", "emulado", "local"}:
            try:
                texto_csv = bytes(contenido).decode("utf-8-sig", errors="replace")
                resultado_ia = extraer_filas_excel_texto(f"CONTENIDO DEL CSV:\n{texto_csv}")
                origen = _filas_desde_ia(resultado_ia)
                proveedor, modelo = resultado_ia["proveedor"], resultado_ia.get("modelo")
                advertencias.extend(resultado_ia.get("advertencias", []))
                if not origen:
                    raise ValueError("La IA no encontró partidos en el CSV.")
            except ValueError as error:
                error_ia = error
                origen = []
        else:
            origen = []
        if not origen:
            origen = _normalizar_filas_tabulares(_leer_tabular(bytes(contenido), extension))
            proveedor, modelo = "lectura local", None
            if error_ia:
                advertencias.append(
                    f"No se pudo usar la IA ({error_ia}). Se aplicó la lectura tabular local. "
                    "Revisa los campos antes de confirmar."
                )
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
