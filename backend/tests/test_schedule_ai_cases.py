import json

from app.services import vision
from app.services.schedule_extractor import _filas_desde_ia, _texto_csv_para_ia


def _fila(fecha, arbitro, evidencia):
    return {
        "fecha": fecha,
        "hora": "18:30",
        "arbitro": arbitro,
        "ciudad_origen": "Valencia",
        "ciudad_destino": "Caracas",
        "cancha": "Gimnasio",
        "medio_transporte": None,
        "cantidad_dias": 1,
        "cantidad_noches": 0,
        "viatico_por_dia": None,
        "hospedaje_total": None,
        "evidencia": evidencia,
        "confianza": 0.95,
        "notas": "",
        "presupuesto": None,
    }


def test_mocked_llm_expands_date_by_referee_matrix(monkeypatch):
    payload = {
        "filas": [
            _fila("2026-11-05", "Pedro Martínez", "Calendario · R4/C2"),
            _fila("2026-11-05", "María González", "Calendario · R4/C3"),
            _fila("2026-11-07", "Pedro Martínez", "Calendario · R5/C2"),
            _fila("2026-11-07", "María González", "Calendario · R5/C3"),
        ],
        "advertencias": [],
    }
    prompts = []
    monkeypatch.setenv("VISION_PROVIDER", "openrouter")
    monkeypatch.setattr(vision, "_llamar_openrouter", lambda messages, vision, schema: (
        prompts.append(messages[1]["content"]) or json.dumps(payload), "mock/model"
    ))

    catalogo = {"arbitros": [{"id": 1, "nombre": "Pedro Martínez"}], "ciudades": [], "canchas": []}
    resultado = vision.extraer_filas_excel_texto("HOJA: Matriz\nR4: Fecha | Pedro | María", catalogo=catalogo)
    filas = _filas_desde_ia(resultado)

    assert len(filas) == 4
    assert {(fila["fecha"], fila["arbitro_texto"]) for fila in filas} == {
        ("2026-11-05", "Pedro Martínez"), ("2026-11-05", "María González"),
        ("2026-11-07", "Pedro Martínez"), ("2026-11-07", "María González"),
    }
    assert "R4/C2" in filas[0]["evidencia"]
    assert prompts
    assert '"nombre": "Pedro Martínez"' in prompts[0]


def test_two_referees_in_one_cell_become_two_assignment_rows():
    filas = _filas_desde_ia({"filas": [_fila("2026-11-05", "Pedro Martínez; María González", "Jornada · R8")]})
    assert [fila["arbitro_texto"] for fila in filas] == ["Pedro Martínez", "María González"]
    assert all(fila["evidencia"] == "Jornada · R8" for fila in filas)


def test_stacked_csv_tables_are_sent_together_with_source_rows(monkeypatch):
    csv = (
        "Calendario\nFECHA,HORA,ARBITRO,CANCHA,CIUDAD\n2026-11-05,18:30,Pedro,Gimnasio,Caracas\n\n"
        "Asignaciones adicionales\nDIA,COLEGIADO,SEDE,LOCALIDAD\n2026-11-07,María,Forum,Valencia\n"
    ).encode()
    texto = _texto_csv_para_ia(csv)
    recibido = {}
    payload = {"filas": [_fila("2026-11-05", "Pedro", "CSV · R3"), _fila("2026-11-07", "María", "CSV · R7")], "advertencias": []}
    monkeypatch.setenv("VISION_PROVIDER", "openrouter")

    def mock_llm(messages, vision, schema):
        recibido["prompt"] = messages[1]["content"]
        return json.dumps(payload), "mock/model"

    monkeypatch.setattr(vision, "_llamar_openrouter", mock_llm)
    resultado = vision.extraer_filas_excel_texto(texto)

    assert "R2: FECHA,HORA,ARBITRO,CANCHA,CIUDAD" in recibido["prompt"]
    assert "R6: DIA,COLEGIADO,SEDE,LOCALIDAD" in recibido["prompt"]
    assert "CABECERA: R2: FECHA,HORA,ARBITRO,CANCHA,CIUDAD" in recibido["prompt"]
    assert "CABECERA: R6: DIA,COLEGIADO,SEDE,LOCALIDAD" in recibido["prompt"]
    assert len(resultado["filas"]) == 2


def test_json_wrapped_in_backticks_is_parsed():
    assert vision._json_objeto('`{"filas": [], "advertencias": []}`') == {"filas": [], "advertencias": []}
    assert vision._json_objeto('```json\n{"filas": []}\n```') == {"filas": []}
