"""Consulta paginada de la bitácora de auditoría."""

from flask import Blueprint, jsonify, request

from ..models import HistorialCambio

bp = Blueprint("historial", __name__)


@bp.get("/historial")
def listar_historial():
    try:
        pagina = int(request.args.get("pagina", request.args.get("page", 1)))
        por_pagina = int(request.args.get("por_pagina", request.args.get("per_page", 20)))
    except (TypeError, ValueError):
        return jsonify({"error": "pagina y por_pagina deben ser números enteros."}), 400

    if pagina < 1 or por_pagina < 1:
        return jsonify({"error": "pagina y por_pagina deben ser mayores que cero."}), 400
    por_pagina = min(por_pagina, 100)

    entidad_id = None
    if "entidad_id" in request.args:
        try:
            entidad_id = int(request.args["entidad_id"])
        except (TypeError, ValueError):
            return jsonify({"error": "entidad_id debe ser un número entero."}), 400

    consulta = HistorialCambio.query
    entidad = request.args.get("entidad", type=str)
    accion = request.args.get("accion", type=str)
    origen = request.args.get("origen", type=str)
    if entidad:
        consulta = consulta.filter(HistorialCambio.entidad == entidad)
    if entidad_id is not None:
        consulta = consulta.filter(HistorialCambio.entidad_id == entidad_id)
    if accion:
        consulta = consulta.filter(HistorialCambio.accion == accion)
    if origen:
        consulta = consulta.filter(HistorialCambio.origen == origen)

    total = consulta.count()
    registros = (
        consulta.order_by(HistorialCambio.fecha.desc(), HistorialCambio.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )
    return jsonify({
        "items": [registro.to_dict() for registro in registros],
        "paginacion": {
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total": total,
            "paginas": (total + por_pagina - 1) // por_pagina,
        },
    }), 200
