"""Utilidades para registrar cambios auditables en la base de datos."""

import json
from typing import Any

from ..database import db
from ..models import HistorialCambio


def _serializar(valor: Any) -> str:
    return json.dumps(valor, ensure_ascii=False, default=str, sort_keys=True)


def _calcular_diff(antes: dict | None, despues: dict | None) -> tuple[dict, dict]:
    """Retorna snapshots limitados a las claves modificadas."""
    anterior = antes or {}
    nuevo = despues or {}
    campos = anterior.keys() | nuevo.keys()
    modificados = [
        campo for campo in campos
        if campo not in anterior or campo not in nuevo or anterior[campo] != nuevo[campo]
    ]
    return (
        {campo: anterior.get(campo) for campo in modificados},
        {campo: nuevo.get(campo) for campo in modificados},
    )


def registrar_cambio(
    entidad: str,
    entidad_id: int,
    accion: str,
    antes: dict | None = None,
    despues: dict | None = None,
    origen: str = "web_admin",
    commit: bool = True,
) -> HistorialCambio:
    """Guarda un cambio, almacenando únicamente los campos que difieren."""
    diff_antes, diff_despues = _calcular_diff(antes, despues)
    registro = HistorialCambio(
        entidad=entidad,
        entidad_id=entidad_id,
        accion=accion,
        antes=_serializar(diff_antes) if diff_antes else None,
        despues=_serializar(diff_despues) if diff_despues else None,
        origen=origen,
    )
    db.session.add(registro)
    try:
        if commit:
            db.session.commit()
        else:
            db.session.flush()
    except Exception:
        db.session.rollback()
        raise
    return registro
