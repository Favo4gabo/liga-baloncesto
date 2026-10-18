"""Endpoint de carga masiva de información logística."""

from flask import Blueprint, jsonify, request

from ..authz import roles_required
from ..services.excel_parser import procesar_archivo_excel

bp = Blueprint("upload", __name__)


@bp.post("/upload-excel")
@roles_required("super_admin", "admin")
def cargar_excel():
    archivo = request.files.get("file")
    if archivo is None or not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Debe adjuntar un archivo .xlsx en el campo 'file'."}), 400
    try:
        resumen = procesar_archivo_excel(archivo.read())
        return jsonify(resumen), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 400


@bp.post("/upload-excel/analizar")
@roles_required("super_admin", "admin")
def analizar_excel():
    """Valida la estructura del libro y devuelve un resumen sin guardar cambios."""
    archivo = request.files.get("file")
    if archivo is None or not archivo.filename or not archivo.filename.lower().endswith(".xlsx"):
        return jsonify({"error": "Debe adjuntar un archivo .xlsx en el campo 'file'."}), 400
    try:
        resumen = procesar_archivo_excel(archivo.read(), guardar=False)
        return jsonify(resumen), 200
    except Exception as error:
        return jsonify({"error": str(error)}), 400
