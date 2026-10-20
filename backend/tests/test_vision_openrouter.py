import requests

from app.services import vision


class FakeResponse:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error

    def json(self):
        return self._body


def test_openrouter_uses_strict_schema_models_and_configured_timeout(monkeypatch):
    captured = {}

    def post(url, **kwargs):
        captured.update(kwargs)
        return FakeResponse(200, {"model": "chosen/model", "choices": [{"message": {"content": '{"filas":[],"advertencias":[]}'} }]})

    monkeypatch.setenv("VISION_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "primary/model")
    monkeypatch.setenv("MIGRATION_AI_MODEL", "primary/model")
    monkeypatch.setenv("OPENROUTER_FALLBACK_MODELS", "fallback/one,fallback/two")
    monkeypatch.setenv("LLM_TIMEOUT_READ", "42")
    monkeypatch.setattr(vision, "_cliente_http", lambda: type("HTTP", (), {"post": staticmethod(post)}))

    content, model = vision._llamar_openrouter([], vision=False, schema={"type": "object"})

    payload = captured["json"]
    assert model == "chosen/model"
    assert content == '{"filas":[],"advertencias":[]}'
    assert payload["models"] == ["primary/model", "fallback/one", "fallback/two"]
    assert payload["provider"] == {"require_parameters": True}
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"] == {"type": "object"}
    assert captured["timeout"] == (10, 42.0)


def test_openrouter_retries_transient_status_three_times(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append(kwargs)
        if len(calls) < 4:
            return FakeResponse(503)
        return FakeResponse(200, {"choices": [{"message": {"content": '{"filas":[],"advertencias":[]}'} }]})

    monkeypatch.setenv("VISION_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(vision, "_cliente_http", lambda: type("HTTP", (), {"post": staticmethod(post)}))
    monkeypatch.setattr(vision.time, "sleep", lambda _: None)

    content, _ = vision._llamar_openrouter([], vision=True, schema={"type": "object"})
    assert len(calls) == 4
    assert '"filas":[]' in content


def test_schedule_schema_and_shared_system_prompt_cover_requested_rules():
    row_schema = vision.HORARIO_SCHEMA["properties"]["filas"]["items"]
    fields = row_schema["properties"]
    assert {"fecha", "hora", "arbitro", "ciudad_origen", "ciudad_destino", "cancha",
            "medio_transporte", "cantidad_dias", "cantidad_noches", "viatico_por_dia",
            "hospedaje_total", "evidencia", "confianza", "notas"}.issubset(fields)
    assert fields["medio_transporte"]["enum"] == ["avion", "terrestre", None]
    prompt = vision.PROMPT_SISTEMA.lower()
    for required_rule in ("dd/mm", "24 horas", "apellido, nombre", "varios árbitros",
                          "no lo deduzcas por", "intersección de matriz"):
        assert required_rule in prompt


def test_catalog_import_uses_shared_openrouter_helper_and_schema(monkeypatch):
    captured = {}
    monkeypatch.setenv("VISION_PROVIDER", "openrouter")

    def call(messages, vision, schema):
        captured.update(messages=messages, vision=vision, schema=schema)
        return '{"estados_ciudades":[],"tarifas_traslado":[],"tarifas_hospedaje":[],"estados_cercanos":[],"arbitros":[],"advertencias":[]}', "mock/model"

    monkeypatch.setattr(vision, "_llamar_openrouter", call)
    resultado = vision.extraer_catalogos_excel("contenido tabular")
    assert resultado["modelo"] == "mock/model"
    assert captured["schema"] is vision.CATALOGOS_SCHEMA
    assert captured["vision"] is False
    assert captured["messages"][0] == {"role": "system", "content": vision.PROMPT_SISTEMA}


def test_image_openrouter_uses_shared_helper_in_vision_mode(monkeypatch):
    captured = {}
    monkeypatch.setenv("VISION_PROVIDER", "openrouter")

    def call(messages, vision, schema):
        captured.update(messages=messages, vision=vision, schema=schema)
        return '{"filas":[],"advertencias":[]}', "mock/vision"

    monkeypatch.setattr(vision, "_llamar_openrouter", call)
    resultado = vision._openrouter(b"fake-image", "image/png")
    assert resultado["modelo"] == "mock/vision"
    assert captured["vision"] is True
    assert captured["schema"] is vision.HORARIO_SCHEMA
    assert captured["messages"][0]["content"] == vision.PROMPT_SISTEMA
