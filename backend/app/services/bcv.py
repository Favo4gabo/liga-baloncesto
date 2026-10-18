"""Consulta y conserva tasas USD/VES publicadas por el BCV."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
import os
import re

import requests

from ..database import db
from ..models import TasaCambioBCV


class _TasaBCVParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._in_dollar = False
        self._depth = 0
        self._strong_depth = 0
        self.values = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "div" and attributes.get("id", "").lower() == "dolar":
            self._in_dollar = True
            self._depth = 1
        elif self._in_dollar:
            if tag == "div":
                self._depth += 1
            if tag == "strong":
                self._strong_depth += 1

    def handle_endtag(self, tag):
        if not self._in_dollar:
            return
        if tag == "strong" and self._strong_depth:
            self._strong_depth -= 1
        elif tag == "div":
            self._depth -= 1
            if self._depth <= 0:
                self._in_dollar = False

    def handle_data(self, data):
        if self._in_dollar and self._strong_depth:
            self.values.append(data.strip())


def consultar_tasa_bcv(fecha_efectiva: date | None = None, registrada_por_id: int | None = None) -> TasaCambioBCV:
    """Consulta la tasa publicada hoy en el BCV y la conserva como dato histórico.

    El portal público del BCV no garantiza un endpoint API estable. Si su HTML cambia
    o no está disponible, la aplicación devuelve un error y no inventa una cotización.
    """
    efectiva = fecha_efectiva or date.today()
    if efectiva != date.today():
        raise ValueError("El portal consultado publica la tasa vigente; para una fecha pasada registra la tasa histórica verificada.")

    url = os.getenv("BCV_URL", "https://www.bcv.org.ve/").strip()
    try:
        response = requests.get(url, timeout=(5, 15), headers={"User-Agent": "ArbiLiga/1.0 (consulta de tasa oficial)"})
        response.raise_for_status()
    except requests.RequestException as error:
        raise ValueError("No fue posible consultar el sitio del BCV. Puedes registrar manualmente la cotización oficial del día.") from error

    parser = _TasaBCVParser()
    parser.feed(response.text)
    texto = " ".join(value for value in parser.values if value)
    match = re.search(r"(?<!\d)(\d{1,3}(?:\.\d{3})*,\d{2,8}|\d+,\d{2,8})(?!\d)", texto)
    if not match:
        raise ValueError("No se reconoció la cotización USD publicada por el BCV; revisa la página y registra la tasa verificada.")
    try:
        rate = Decimal(match.group(1).replace(".", "").replace(",", "."))
    except InvalidOperation as error:
        raise ValueError("El BCV devolvió una cotización con formato inesperado.") from error
    if not rate.is_finite() or rate <= 0:
        raise ValueError("La tasa obtenida del BCV no es válida.")

    registro = db.session.get(TasaCambioBCV, efectiva) or TasaCambioBCV(fecha=efectiva)
    registro.ves_por_usd = rate
    registro.fuente = "BCV"
    registro.url_fuente = url
    registro.registrada_por_id = registrada_por_id
    db.session.add(registro)
    db.session.commit()
    return registro


def tasa_para_fecha(fecha: date, auto_consultar_hoy: bool = True) -> TasaCambioBCV | None:
    """Retorna la última tasa oficial vigente en esa fecha (fines de semana incluidos)."""
    registro = TasaCambioBCV.query.filter(TasaCambioBCV.fecha <= fecha).order_by(TasaCambioBCV.fecha.desc()).first()
    if registro or not auto_consultar_hoy or fecha != date.today():
        return registro
    try:
        return consultar_tasa_bcv(fecha)
    except ValueError:
        return None
