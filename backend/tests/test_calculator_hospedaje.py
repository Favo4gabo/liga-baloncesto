from decimal import Decimal
from types import SimpleNamespace

from app.services import calculator


def test_explicit_hospedaje_total_replaces_missing_city_rate(monkeypatch):
    arbitro = SimpleNamespace(ciudad_origen_id=1)
    partido = SimpleNamespace(ciudad_juego_id=2)

    class FakeArbitro: pass
    class FakePartido: pass
    class FakeParametro: pass

    class FakeSession:
        def get(self, model, _key):
            if model is FakeArbitro:
                return arbitro
            if model is FakePartido:
                return partido
            return None

    class FakeQuery:
        def filter_by(self, **_filters):
            return self

        def first(self):
            return None

    class FakeTarifaHospedaje:
        query = FakeQuery()

    monkeypatch.setattr(calculator, "Arbitro", FakeArbitro)
    monkeypatch.setattr(calculator, "Partido", FakePartido)
    monkeypatch.setattr(calculator, "Parametro", FakeParametro)
    monkeypatch.setattr(calculator, "TarifaHospedaje", FakeTarifaHospedaje)
    monkeypatch.setattr(calculator.db, "session", FakeSession())
    monkeypatch.setattr(calculator, "_requerir_tarifa", lambda tipo, medio: Decimal("10" if tipo == "externo" else "5"))

    calculo = calculator.calcular_viaticos_asignacion(
        1, 1, cantidad_noches=2, cantidad_dias=1, medio_transporte="taxi",
        viatico_por_dia=25, hospedaje_total=95,
    )

    assert calculo["costo_estadia"] == 95.0
    assert calculo["costo_hospedaje_por_noche"] == 47.5
    assert calculo["costo_total"] == 150.0


def test_city_hotel_rate_is_still_required_without_file_override(monkeypatch):
    arbitro = SimpleNamespace(ciudad_origen_id=1)
    partido = SimpleNamespace(ciudad_juego_id=2)

    class FakeArbitro: pass
    class FakePartido: pass
    class FakeParametro: pass

    class FakeSession:
        def get(self, model, _key):
            return arbitro if model is FakeArbitro else partido if model is FakePartido else None

    class FakeQuery:
        def filter_by(self, **_filters):
            return self

        def first(self):
            return None

    class FakeTarifaHospedaje:
        query = FakeQuery()

    monkeypatch.setattr(calculator, "Arbitro", FakeArbitro)
    monkeypatch.setattr(calculator, "Partido", FakePartido)
    monkeypatch.setattr(calculator, "Parametro", FakeParametro)
    monkeypatch.setattr(calculator, "TarifaHospedaje", FakeTarifaHospedaje)
    monkeypatch.setattr(calculator.db, "session", FakeSession())
    monkeypatch.setattr(calculator, "_requerir_tarifa", lambda _tipo, _medio: Decimal("10"))

    try:
        calculator.calcular_viaticos_asignacion(
            1, 1, cantidad_noches=1, cantidad_dias=1, medio_transporte="taxi", viatico_por_dia=25,
        )
    except ValueError as error:
        assert "Falta configurar la tarifa de hospedaje" in str(error)
    else:
        raise AssertionError("Debió exigir la tarifa de hospedaje sin un importe explícito.")
