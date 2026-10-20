"""Importación atómica del libro maestro definido para la liga."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from io import BytesIO
from typing import Any, BinaryIO
import re
import unicodedata

import pandas as pd

from ..database import db
from ..models import (Aeropuerto, Arbitro, Ciudad, Estado, EstadoCercano, Parametro, Partido,
                       DistanciaCiudad, TarifaHospedaje, TarifaTraslado, UbicacionCancha)

HOJAS = {
    "Estados": {"nombre"}, "Ciudades": {"nombre", "estado"},
    "TarifasTraslado": {"tipo", "medio", "costo_base"},
    "TarifasHospedaje": {"ciudad", "costo_noche"}, "Parametros": {"clave", "valor"},
    "EstadosCercanos": {"estado_a", "estado_b"},
    "Arbitros": {"nombre", "apellido", "telefono", "email", "ciudad_origen"},
    "Partidos": {"fecha_hora", "estadio_cancha", "ciudad_juego"},
}

HOJAS_OPCIONALES = {
    "DistanciasCiudades": {"ciudad_origen", "ciudad_destino", "distancia_km"},
    "UbicacionesCancha": {"estadio_cancha", "ciudad", "direccion", "latitud", "longitud"},
    "Aeropuertos": {"estado", "ciudad_sede", "nombre", "codigo_iata", "latitud", "longitud"},
}


def _normalizar(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor).strip())
    return "".join(c for c in texto if not unicodedata.combining(c)).casefold()


def _vacio(valor: Any) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip()) or pd.isna(valor)


def _texto(valor: Any, campo: str, obligatorio: bool = True) -> str | None:
    if _vacio(valor):
        if obligatorio:
            raise ValueError(f"El campo '{campo}' es obligatorio.")
        return None
    return str(valor).strip()


def _decimal(valor: Any, campo: str) -> Decimal:
    try:
        numero = Decimal(str(_texto(valor, campo)))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"El campo '{campo}' debe ser numérico.") from error
    if not numero.is_finite() or numero < 0:
        raise ValueError(f"El campo '{campo}' debe ser un importe válido no negativo.")
    return numero


def _coordenada(valor: Any, campo: str, limite: Decimal) -> Decimal:
    """Valida coordenadas: a diferencia de importes, longitud puede ser negativa."""
    try:
        numero = Decimal(str(_texto(valor, campo)))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"El campo '{campo}' debe ser numérico.") from error
    if not numero.is_finite() or abs(numero) > limite:
        raise ValueError(f"El campo '{campo}' está fuera de rango.")
    return numero


def _filas(libro: dict[str, pd.DataFrame], hoja: str) -> list[dict[str, Any]]:
    marco = libro[hoja].copy()
    columnas = [_normalizar(columna) for columna in marco.columns]
    if len(columnas) != len(set(columnas)):
        raise ValueError(f"La hoja '{hoja}' tiene cabeceras duplicadas.")
    faltantes = (HOJAS.get(hoja) or HOJAS_OPCIONALES[hoja]) - set(columnas)
    if faltantes:
        raise ValueError(f"Faltan cabeceras en '{hoja}': {', '.join(sorted(faltantes))}.")
    marco.columns = columnas
    return [fila.to_dict() for _, fila in marco.dropna(how="all").iterrows()]


def _buscar(mapa: dict[str, Any], valor: Any, campo: str) -> Any:
    texto = _texto(valor, campo)
    registro = mapa.get(_normalizar(texto))
    if registro is None:
        raise ValueError(f"'{texto}' indicado en '{campo}' no existe.")
    return registro


def _procesar_libro_estructurado(archivo: bytes | bytearray | BinaryIO, guardar: bool = True) -> dict[str, Any]:
    """Valida el libro y opcionalmente lo guarda de forma atómica."""
    origen = BytesIO(archivo) if isinstance(archivo, (bytes, bytearray)) else archivo
    if hasattr(origen, "seek"):
        origen.seek(0)
    try:
        libro = pd.read_excel(origen, sheet_name=None, engine="openpyxl")
        faltantes = [nombre for nombre in HOJAS if nombre not in libro]
        if faltantes:
            raise ValueError("Faltan hojas requeridas: " + ", ".join(faltantes))
        datos = {hoja: _filas(libro, hoja) for hoja in HOJAS}
        datos.update({hoja: _filas(libro, hoja) for hoja in HOJAS_OPCIONALES if hoja in libro})
        resumen = {"estados": 0, "ciudades": 0, "tarifas_traslado": 0, "tarifas_hospedaje": 0,
                   "parametros": 0, "estados_cercanos": 0, "arbitros": 0, "partidos": 0,
                   "distancias_ciudades": 0, "ubicaciones_cancha": 0, "aeropuertos": 0}

        estados = {_normalizar(x.nombre): x for x in Estado.query.all()}
        for fila in datos["Estados"]:
            nombre = _texto(fila["nombre"], "nombre")
            estados.setdefault(_normalizar(nombre), Estado(nombre=nombre))
            if estados[_normalizar(nombre)] not in db.session:
                db.session.add(estados[_normalizar(nombre)])
            resumen["estados"] += 1
        db.session.flush()
        ciudades = {_normalizar(f"{x.nombre}|{x.estado.nombre}"): x for x in Ciudad.query.join(Estado).all()}
        for fila in datos["Ciudades"]:
            nombre, estado = _texto(fila["nombre"], "nombre"), _buscar(estados, fila["estado"], "estado")
            clave = _normalizar(f"{nombre}|{estado.nombre}")
            ciudad = ciudades.get(clave)
            if ciudad is None:
                ciudad = Ciudad(nombre=nombre, estado=estado); db.session.add(ciudad); ciudades[clave] = ciudad
            resumen["ciudades"] += 1
        db.session.flush()
        ciudades_nombre = {_normalizar(x.nombre): x for x in ciudades.values()}
        if len(ciudades_nombre) != len(ciudades):
            raise ValueError("Hay ciudades repetidas en distintos estados; use nombres de ciudad únicos en este Excel.")
        for fila in datos.get("Aeropuertos", []):
            estado = _buscar(estados, fila["estado"], "estado")
            iata = _texto(fila["codigo_iata"], "codigo_iata").upper()
            if len(iata) != 3 or not iata.isalpha():
                raise ValueError("Aeropuertos: codigo_iata debe tener tres letras.")
            aeropuerto = Aeropuerto.query.filter_by(codigo_iata=iata).first() or Aeropuerto(codigo_iata=iata)
            aeropuerto.estado_id = estado.id
            aeropuerto.ciudad_sede = _texto(fila["ciudad_sede"], "ciudad_sede")
            aeropuerto.nombre = _texto(fila["nombre"], "nombre")
            aeropuerto.latitud = _coordenada(fila["latitud"], "latitud", Decimal("90"))
            aeropuerto.longitud = _coordenada(fila["longitud"], "longitud", Decimal("180"))
            aeropuerto.principal = True
            db.session.add(aeropuerto); resumen["aeropuertos"] += 1
        for fila in datos.get("DistanciasCiudades", []):
            origen = _buscar(ciudades_nombre, fila["ciudad_origen"], "ciudad_origen")
            destino = _buscar(ciudades_nombre, fila["ciudad_destino"], "ciudad_destino")
            if origen.id == destino.id:
                raise ValueError("DistanciasCiudades no admite una ciudad como origen y destino.")
            menor, mayor = sorted((origen.id, destino.id))
            distancia = DistanciaCiudad.query.filter_by(ciudad_origen_id=menor, ciudad_destino_id=mayor).first()
            distancia = distancia or DistanciaCiudad(ciudad_origen_id=menor, ciudad_destino_id=mayor)
            distancia.distancia_km = _decimal(fila["distancia_km"], "distancia_km")
            db.session.add(distancia); resumen["distancias_ciudades"] += 1
        for fila in datos.get("UbicacionesCancha", []):
            ciudad = _buscar(ciudades_nombre, fila["ciudad"], "ciudad")
            nombre = _texto(fila["estadio_cancha"], "estadio_cancha")
            cancha = UbicacionCancha.query.filter_by(nombre_cancha=nombre, ciudad_id=ciudad.id).first()
            cancha = cancha or UbicacionCancha(nombre_cancha=nombre, ciudad_id=ciudad.id)
            cancha.direccion = _texto(fila["direccion"], "direccion", False)
            cancha.latitud = _coordenada(fila["latitud"], "latitud", Decimal("90")) if not _vacio(fila["latitud"]) else None
            cancha.longitud = _coordenada(fila["longitud"], "longitud", Decimal("180")) if not _vacio(fila["longitud"]) else None
            db.session.add(cancha); resumen["ubicaciones_cancha"] += 1

        tarifas = {(x.tipo, x.medio): x for x in TarifaTraslado.query.all()}
        for fila in datos["TarifasTraslado"]:
            tipo, medio = _texto(fila["tipo"], "tipo").lower(), _texto(fila["medio"], "medio").lower()
            if tipo not in {"externo", "interno"} or medio not in {"avion", "taxi"}:
                raise ValueError("TarifasTraslado: tipo debe ser externo/interno y medio avion/taxi.")
            tarifa = tarifas.get((tipo, medio)) or TarifaTraslado(tipo=tipo, medio=medio)
            tarifa.costo_base = _decimal(fila["costo_base"], "costo_base"); db.session.add(tarifa)
            resumen["tarifas_traslado"] += 1
        for fila in datos["TarifasHospedaje"]:
            ciudad = _buscar(ciudades_nombre, fila["ciudad"], "ciudad")
            tarifa = TarifaHospedaje.query.filter_by(ciudad_id=ciudad.id).first() or TarifaHospedaje(ciudad=ciudad)
            tarifa.costo_noche = _decimal(fila["costo_noche"], "costo_noche"); db.session.add(tarifa)
            resumen["tarifas_hospedaje"] += 1
        for fila in datos["Parametros"]:
            clave = _texto(fila["clave"], "clave")
            parametro = db.session.get(Parametro, clave) or Parametro(clave=clave)
            parametro.valor = _decimal(fila["valor"], "valor"); db.session.add(parametro)
            resumen["parametros"] += 1
        for fila in datos["EstadosCercanos"]:
            a, b = _buscar(estados, fila["estado_a"], "estado_a"), _buscar(estados, fila["estado_b"], "estado_b")
            if a.id == b.id:
                raise ValueError("Un estado no puede declararse cercano a sí mismo.")
            menor, mayor = sorted((a.id, b.id))
            if not EstadoCercano.query.filter_by(estado_a_id=menor, estado_b_id=mayor).first():
                db.session.add(EstadoCercano(estado_a_id=menor, estado_b_id=mayor))
            resumen["estados_cercanos"] += 1
        arbitros_existentes = {
            (_normalizar(x.nombre), _normalizar(x.apellido), x.ciudad_origen_id): x
            for x in Arbitro.query.all()
        }
        for fila in datos["Arbitros"]:
            nombre = _texto(fila["nombre"], "nombre")
            apellido = _texto(fila["apellido"], "apellido")
            ciudad_origen = _buscar(ciudades_nombre, fila["ciudad_origen"], "ciudad_origen")
            clave_arbitro = (_normalizar(nombre), _normalizar(apellido), ciudad_origen.id)
            arbitro = arbitros_existentes.get(clave_arbitro)
            telefono = _texto(fila["telefono"], "telefono", False)
            email = _texto(fila["email"], "email", False)
            if arbitro is None:
                arbitro = Arbitro(nombre=nombre, apellido=apellido, telefono=telefono, email=email,
                                  ciudad_origen=ciudad_origen)
                db.session.add(arbitro)
                arbitros_existentes[clave_arbitro] = arbitro
            else:
                arbitro.telefono = telefono or arbitro.telefono
                arbitro.email = email or arbitro.email
            resumen["arbitros"] += 1
        for fila in datos["Partidos"]:
            fecha = pd.to_datetime(fila["fecha_hora"], errors="coerce")
            if pd.isna(fecha):
                raise ValueError("El campo 'fecha_hora' debe tener un formato válido.")
            fecha_hora = fecha.to_pydatetime()
            cancha = _texto(fila["estadio_cancha"], "estadio_cancha")
            ciudad_juego = _buscar(ciudades_nombre, fila["ciudad_juego"], "ciudad_juego")
            partido = Partido.query.filter_by(
                fecha_hora=fecha_hora, estadio_cancha=cancha, ciudad_juego_id=ciudad_juego.id
            ).first()
            if partido is None:
                db.session.add(Partido(fecha_hora=fecha_hora, estadio_cancha=cancha, ciudad_juego=ciudad_juego))
            resumen["partidos"] += 1
        if guardar:
            db.session.commit()
        else:
            db.session.rollback()
        return {"status": "success", "insertados_o_actualizados": resumen}
    except Exception:
        db.session.rollback()
        raise


def _clave_cabecera(valor: Any) -> str:
    texto = unicodedata.normalize("NFKD", str(valor or "").strip().casefold())
    texto = "".join(caracter for caracter in texto if not unicodedata.combining(caracter))
    return re.sub(r"[^a-z0-9]+", "", texto)


def _numero_importe(valor: Any, campo: str) -> Decimal:
    """Acepta valores numéricos de Excel y cadenas con formato monetario español."""
    if isinstance(valor, str):
        texto = re.sub(r"[^0-9,.+-]", "", valor.strip())
        if "," in texto and "." in texto:
            if texto.rfind(",") > texto.rfind("."):
                texto = texto.replace(".", "").replace(",", ".")
            else:
                texto = texto.replace(",", "")
        elif "," in texto:
            texto = texto.replace(",", ".")
        valor = texto
    return _decimal(valor, campo)


_COLUMNAS_BLOQUES = {
    "ciudades": {
        "estado": {"estado", "entidad", "estadofederal"},
        "ciudad": {"ciudad", "municipio", "localidad"},
    },
    "traslados": {
        "tipo": {"tipodetraslado", "tipotraslado", "tipodemovilidad", "tipodetraslado"},
        "costo": {"costobaseusd", "costobase", "tarifausd", "costousd", "costo"},
    },
    "hospedaje": {
        "ciudad": {"ciudadsede", "ciudad", "sede"},
        "costo": {"costohotelpornocheusd", "costonocheusd", "costohotelpornoche", "costopornoche", "costonoche"},
        "viatico": {"viaticodiariosugeridousd", "viaticopordiausd", "viaticodiariosugerido", "viaticodiario", "viaticopordia"},
    },
    "cercanos": {
        "origen": {"estadoorigen", "estadoa"},
        "destino": {"estadodestino", "estadob"},
    },
    "arbitros": {
        "nombre": {"nombre", "nombres", "firstname", "name"},
        "apellido": {"apellido", "apellidos", "surname", "lastname", "familyname"},
        "telefono": {"telefono", "telefonocelular", "celular", "phone", "mobile"},
        "email": {"email", "correo", "correoelectronico"},
        "ciudad_origen": {"ciudaddeorigen", "ciudadorigen", "origen", "ciudadprocedencia", "ciudadresidencia"},
    },
}


def _indices_cabecera(valores: list[Any], tipo: str) -> dict[str, int]:
    mapa = {}
    for indice, valor in enumerate(valores):
        columna = _clave_cabecera(valor)
        for campo, alias in _COLUMNAS_BLOQUES[tipo].items():
            coincidencia_aproximada = any(
                len(columna) >= 8 and SequenceMatcher(None, columna, alternativa).ratio() >= 0.9
                for alternativa in alias
            )
            if columna in alias or coincidencia_aproximada:
                mapa.setdefault(campo, indice)
    obligatorias = {
        "ciudades": {"estado", "ciudad"},
        "traslados": {"tipo", "costo"},
        "hospedaje": {"ciudad", "costo"},
        "cercanos": {"origen", "destino"},
        "arbitros": {"nombre", "apellido", "ciudad_origen"},
    }[tipo]
    return mapa if obligatorias.issubset(mapa) else {}


def _valor_celda(fila: list[Any], indice: int | None) -> Any:
    return fila[indice] if indice is not None and indice < len(fila) else None


def _extraer_bloques_excel(contenido: bytes) -> dict[str, list[dict[str, Any]]]:
    """Detecta tablas por sus encabezados aunque estén apiladas en una misma hoja."""
    try:
        hojas = pd.read_excel(BytesIO(contenido), sheet_name=None, header=None, dtype=object, engine="openpyxl")
    except Exception as error:
        raise ValueError(f"No se pudo leer el archivo Excel: {error}") from error

    bloques = {tipo: [] for tipo in _COLUMNAS_BLOQUES}
    for hoja in hojas.values():
        filas = hoja.values.tolist()
        for indice_fila, fila in enumerate(filas):
            for tipo in _COLUMNAS_BLOQUES:
                indices = _indices_cabecera(fila, tipo)
                if not indices:
                    continue
                relevantes = list(indices.values())
                for indice_dato in range(indice_fila + 1, len(filas)):
                    datos = filas[indice_dato]
                    if all(_vacio(_valor_celda(datos, columna)) for columna in relevantes):
                        break
                    registro = {campo: _valor_celda(datos, columna) for campo, columna in indices.items()}
                    if any(not _vacio(valor) for valor in registro.values()):
                        bloques[tipo].append(registro)
                break
    return bloques


def _texto_excel_para_ia(contenido: bytes) -> tuple[str, bool]:
    """Serializa celdas con coordenadas y detecta encabezados de árbitros dudosos."""
    hojas = pd.read_excel(BytesIO(contenido), sheet_name=None, header=None, dtype=object, engine="openpyxl")
    secciones, posible_tabla_arbitros = [], False
    alias_nombre = {"nombre", "nombres", "firstname", "name", "nombrecompleto", "fullname"}
    alias_apellido = {"apellido", "apellidos", "surname", "lastname", "familyname"}
    alias_contacto = {"telefono", "telefonocelular", "celular", "phone", "mobile"}
    for nombre_hoja, hoja in hojas.items():
        lineas = []
        for indice, valores in enumerate(hoja.itertuples(index=False, name=None), start=1):
            celdas = [
                f"{columna + 1}={str(valor).strip()}"
                for columna, valor in enumerate(valores)
                if not _vacio(valor)
            ]
            if celdas:
                lineas.append(f"fila {indice}: " + " | ".join(celdas))
            encabezados = {_clave_cabecera(valor) for valor in valores if not _vacio(valor)}
            tiene_nombre = bool(encabezados & alias_nombre)
            tiene_apellido = bool(encabezados & (alias_apellido | {"nombrecompleto", "fullname"}))
            tiene_contacto = bool(encabezados & alias_contacto)
            tiene_ciudad_origen = any(
                "ciudad" in encabezado and any(termino in encabezado for termino in ("origen", "procedencia", "residencia"))
                for encabezado in encabezados
            )
            if tiene_nombre and tiene_apellido and (tiene_contacto or tiene_ciudad_origen):
                posible_tabla_arbitros = True
        secciones.append(f"HOJA: {nombre_hoja}\n" + "\n".join(lineas))
    return "\n\n".join(secciones), posible_tabla_arbitros


def _aplicar_resultado_ia(bloques: dict[str, list[dict[str, Any]]], resultado: dict[str, Any]) -> None:
    if not bloques["ciudades"]:
        bloques["ciudades"] = [
            {"estado": fila.get("estado"), "ciudad": fila.get("ciudad")}
            for fila in resultado.get("estados_ciudades", []) if isinstance(fila, dict)
        ]
    if not bloques["traslados"]:
        bloques["traslados"] = [
            {"tipo": fila.get("tipo"), "costo": fila.get("costo_base")}
            for fila in resultado.get("tarifas_traslado", []) if isinstance(fila, dict)
        ]
    if not bloques["hospedaje"]:
        bloques["hospedaje"] = [
            {"ciudad": fila.get("ciudad"), "costo": fila.get("costo_noche"), "viatico": fila.get("viatico_por_dia")}
            for fila in resultado.get("tarifas_hospedaje", []) if isinstance(fila, dict)
        ]
    if not bloques["cercanos"]:
        bloques["cercanos"] = [
            {"origen": fila.get("estado_a"), "destino": fila.get("estado_b")}
            for fila in resultado.get("estados_cercanos", []) if isinstance(fila, dict)
        ]
    if not bloques["arbitros"]:
        bloques["arbitros"] = [
            {
                "nombre": fila.get("nombre"), "apellido": fila.get("apellido"),
                "telefono": fila.get("telefono"), "email": fila.get("email"),
                "ciudad_origen": fila.get("ciudad_origen"),
            }
            for fila in resultado.get("arbitros", []) if isinstance(fila, dict)
        ]


def _normalizar_tipo_traslado(valor: Any) -> tuple[str, str]:
    tipo = _clave_cabecera(valor)
    if "local" in tipo or "movilizacion" in tipo:
        return "interno", "taxi"
    if "avion" in tipo or "aereo" in tipo:
        return "externo", "avion"
    if "taxi" in tipo or "terrestre" in tipo:
        return "externo", "taxi"
    raise ValueError(f"No reconozco el tipo de traslado '{valor}'. Usa una descripción local, taxi o avión.")


def _normalizar_libro_por_bloques(bloques: dict[str, list[dict[str, Any]]]) -> bytes | None:
    """Convierte el diseño visual de tablas apiladas a la plantilla interna.

    Es especialmente útil para libros de liga que agrupan ciudades, tarifas,
    rutas y árbitros por bloques en una sola hoja en vez de usar pestañas.
    """
    if not any(bloques[tipo] for tipo in ("ciudades", "traslados", "hospedaje", "cercanos", "arbitros")):
        return None

    ciudades, estados = [], []
    estados_vistos, ciudades_vistas = set(), set()
    for fila in bloques["ciudades"]:
        estado = _texto(fila.get("estado"), "estado")
        ciudad = _texto(fila.get("ciudad"), "ciudad")
        if _normalizar(estado) not in estados_vistos:
            estados.append({"nombre": estado})
            estados_vistos.add(_normalizar(estado))
        clave_ciudad = _normalizar(f"{ciudad}|{estado}")
        if clave_ciudad not in ciudades_vistas:
            ciudades.append({"nombre": ciudad, "estado": estado})
            ciudades_vistas.add(clave_ciudad)

    cercanos = []
    for fila in bloques["cercanos"]:
        origen = _texto(fila.get("origen"), "estado_origen")
        destino = _texto(fila.get("destino"), "estado_destino")
        cercanos.append({"estado_a": origen, "estado_b": destino})
        for nombre in (origen, destino):
            if _normalizar(nombre) not in estados_vistos:
                estados.append({"nombre": nombre})
                estados_vistos.add(_normalizar(nombre))

    tarifas = {}
    for fila in bloques["traslados"]:
        tipo, medio = _normalizar_tipo_traslado(fila.get("tipo"))
        costo = _numero_importe(fila.get("costo"), "costo_base")
        tarifas[(tipo, medio)] = {"tipo": tipo, "medio": medio, "costo_base": costo}

    hoteles, viaticos = [], set()
    for fila in bloques["hospedaje"]:
        ciudad = _texto(fila.get("ciudad"), "ciudad_sede")
        hoteles.append({"ciudad": ciudad, "costo_noche": _numero_importe(fila.get("costo"), "costo_noche")})
        if not _vacio(fila.get("viatico")):
            viaticos.add(_numero_importe(fila.get("viatico"), "viatico_diario"))
    if len(viaticos) > 1:
        raise ValueError(
            "El archivo tiene distintos viáticos diarios por ciudad, pero el catálogo actual usa una tarifa global. "
            "Unifica ese valor en el Excel antes de importarlo."
        )
    parametros = [{"clave": "viatico_por_dia", "valor": next(iter(viaticos))}] if viaticos else []

    arbitros = []
    for fila in bloques["arbitros"]:
        if _vacio(fila.get("nombre")) and _vacio(fila.get("apellido")):
            continue
        arbitros.append({
            "nombre": _texto(fila.get("nombre"), "nombre"),
            "apellido": _texto(fila.get("apellido"), "apellido"),
            "telefono": _texto(fila.get("telefono"), "telefono", False),
            "email": _texto(fila.get("email"), "email", False),
            "ciudad_origen": _texto(fila.get("ciudad_origen"), "ciudad_origen"),
        })

    hojas = {
        "Estados": pd.DataFrame(estados, columns=["nombre"]),
        "Ciudades": pd.DataFrame(ciudades, columns=["nombre", "estado"]),
        "TarifasTraslado": pd.DataFrame(list(tarifas.values()), columns=["tipo", "medio", "costo_base"]),
        "TarifasHospedaje": pd.DataFrame(hoteles, columns=["ciudad", "costo_noche"]),
        "Parametros": pd.DataFrame(parametros, columns=["clave", "valor"]),
        "EstadosCercanos": pd.DataFrame(cercanos, columns=["estado_a", "estado_b"]),
        "Arbitros": pd.DataFrame(arbitros, columns=["nombre", "apellido", "telefono", "email", "ciudad_origen"]),
        "Partidos": pd.DataFrame(columns=["fecha_hora", "estadio_cancha", "ciudad_juego"]),
    }
    salida = BytesIO()
    with pd.ExcelWriter(salida, engine="openpyxl") as escritor:
        for nombre, marco in hojas.items():
            marco.to_excel(escritor, sheet_name=nombre, index=False)
    return salida.getvalue()


def procesar_archivo_excel(archivo: bytes | bytearray | BinaryIO, guardar: bool = True) -> dict[str, Any]:
    """Importa libro con pestañas estándar o tablas apiladas en una sola hoja."""
    if isinstance(archivo, (bytes, bytearray)):
        contenido = bytes(archivo)
    else:
        if hasattr(archivo, "seek"):
            archivo.seek(0)
        contenido = archivo.read()
        if hasattr(archivo, "seek"):
            archivo.seek(0)
    if not contenido:
        raise ValueError("El archivo Excel está vacío.")

    try:
        nombres_hojas = set(pd.read_excel(BytesIO(contenido), sheet_name=None, engine="openpyxl").keys())
    except Exception as error:
        raise ValueError(f"No se pudo leer el archivo Excel: {error}") from error

    if set(HOJAS).issubset(nombres_hojas):
        return _procesar_libro_estructurado(contenido, guardar)

    bloques = _extraer_bloques_excel(contenido)
    resultado_ia = None
    if not bloques["arbitros"]:
        texto_libro, posible_tabla_arbitros = _texto_excel_para_ia(contenido)
        if posible_tabla_arbitros:
            from .vision import extraer_catalogos_excel

            resultado_ia = extraer_catalogos_excel(texto_libro)
            _aplicar_resultado_ia(bloques, resultado_ia)
    libro_normalizado = _normalizar_libro_por_bloques(bloques)
    if libro_normalizado is not None:
        resultado = _procesar_libro_estructurado(libro_normalizado, guardar)
        resultado["origen"] = "ia_tablas_apiladas" if resultado_ia else "tablas_apiladas"
        if resultado_ia:
            resultado["proveedor"] = resultado_ia.get("proveedor")
            resultado["modelo"] = resultado_ia.get("modelo")
        advertencia = (
            f"La IA ({resultado_ia['proveedor']} · {resultado_ia['modelo']}) ayudó a interpretar la tabla de árbitros. "
            if resultado_ia else "Se reconocieron automáticamente los bloques tabulares del libro. "
        )
        resultado["advertencias"] = [advertencia + "Revisa el resumen antes de confirmar la importación."]
        return resultado

    # Conserva los mensajes detallados de cabeceras/hojas faltantes del formato original.
    return _procesar_libro_estructurado(contenido, guardar)
