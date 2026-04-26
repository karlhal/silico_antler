from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import ALLOWED_CORS_HEADERS, ALLOWED_CORS_METHODS, ALLOWED_ORIGINS, SHOW_API_DOCS, TRUSTED_HOSTS, app

client = TestClient(app)


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


def test_health() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready() -> None:
    response = client.get("/api/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["presets_loaded"] >= 3


def test_default_cors_origins_include_local_dev() -> None:
    assert "http://localhost:5173" in ALLOWED_ORIGINS


def test_default_cors_policy_is_least_privilege() -> None:
    assert ALLOWED_CORS_METHODS == ["GET", "POST", "OPTIONS"]
    assert ALLOWED_CORS_HEADERS == ["Accept", "Content-Type", "Origin"]


def test_default_trusted_hosts_are_local_only() -> None:
    assert TRUSTED_HOSTS == ["localhost", "127.0.0.1", "testserver"]


def test_root_docs_field_matches_runtime_configuration() -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert ("docs" in payload) is SHOW_API_DOCS


def test_rejects_untrusted_host_header() -> None:
    response = client.get("/api/health", headers={"host": "evil.example.com"})
    assert response.status_code == 400


def test_presets_available() -> None:
    response = client.get("/api/v1/demo/presets")
    assert response.status_code == 200
    data = response.json()
    assert "presets" in data
    assert len(data["presets"]) >= 3
    assert data["presets"][0]["preset_id"] == "deck_scenario"


def test_deck_scenario_is_tuned_to_pitch_location() -> None:
    response = client.get("/api/v1/demo/presets")
    assert response.status_code == 200
    deck = next(p for p in response.json()["presets"] if p["preset_id"] == "deck_scenario")
    best = deck["landscape"]["best_point"]

    assert abs(best["temperature_c"] - 58.0) <= 1.5
    assert abs(best["meoh_pct"] - 24.0) <= 1.5
    assert 4.3 <= best["optimization_metric_s"] <= 4.8


def test_simulate_is_deterministic() -> None:
    payload = {
        "preset_id": "photostability_panel",
        "temperature_c": 47.0,
        "meoh_pct": 31.5,
    }
    response_a = client.post("/api/v1/demo/simulate", json=payload)
    response_b = client.post("/api/v1/demo/simulate", json=payload)

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json() == response_b.json()
    assert "optimization_metric_s" in response_a.json()["summary_metrics"]


def test_simulate_rejects_out_of_range_input() -> None:
    payload = {
        "preset_id": "photostability_panel",
        "temperature_c": 100.0,
        "meoh_pct": 31.5,
    }
    response = client.post("/api/v1/demo/simulate", json=payload)
    assert response.status_code == 422


def test_contact_rejects_bad_email() -> None:
    payload = {
        "name": "Alice",
        "email": "not-an-email",
        "company": "Silico",
        "message": "I want to book a pilot call this month.",
    }
    response = client.post("/api/v1/contact", json=payload)
    assert response.status_code == 422


def test_contact_returns_503_when_delivery_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("CONTACT_WEBHOOK_URL", raising=False)

    payload = {
        "name": "Alice",
        "email": "alice@example.com",
        "company": "Silico",
        "message": "I want to book a pilot call this month.",
    }
    response = client.post("/api/v1/contact", json=payload)
    assert response.status_code == 503
    assert "Contact delivery is not configured." in response.json()["detail"]


def test_contact_logs_only_company_name(caplog, monkeypatch) -> None:
    monkeypatch.delenv("CONTACT_EMAIL", raising=False)
    monkeypatch.delenv("CONTACT_WEBHOOK_URL", raising=False)

    payload = {
        "name": "Alice",
        "email": "alice@example.com",
        "company": "Silico",
        "message": "I want to book a pilot call this month.",
    }

    with caplog.at_level("INFO", logger="silico.api"):
        client.post("/api/v1/contact", json=payload)

    assert "Alice" not in caplog.text
    assert "alice@example.com" not in caplog.text
    assert "company=Silico" in caplog.text


def test_contact_sends_smtp_email_when_configured(monkeypatch) -> None:
    sent: dict[str, str | int | tuple[str, str] | bool] = {}

    class DummySMTP:
        def __init__(self, host: str, port: int, timeout: float) -> None:
            sent["host"] = host
            sent["port"] = port
            sent["timeout"] = int(timeout)

        def __enter__(self) -> "DummySMTP":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def ehlo(self) -> None:
            sent["ehlo"] = True

        def starttls(self) -> None:
            sent["starttls"] = True

        def login(self, username: str, password: str) -> None:
            sent["login"] = (username, password)

        def send_message(self, message) -> None:
            sent["to"] = str(message["To"])
            sent["from"] = str(message["From"])
            sent["reply_to"] = str(message["Reply-To"])
            sent["subject"] = str(message["Subject"])

    monkeypatch.setenv("CONTACT_EMAIL", "owner@example.com")
    monkeypatch.delenv("CONTACT_WEBHOOK_URL", raising=False)
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "smtp-user")
    monkeypatch.setenv("SMTP_PASSWORD", "smtp-pass")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "no-reply@example.com")
    monkeypatch.setenv("SMTP_USE_SSL", "false")
    monkeypatch.setenv("SMTP_USE_STARTTLS", "true")
    monkeypatch.setattr("app.contact_delivery.smtplib.SMTP", DummySMTP)

    payload = {
        "name": "Alice",
        "email": "alice@example.com",
        "company": "Silico",
        "message": "I want to book a pilot call this month.",
    }
    response = client.post("/api/v1/contact", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert sent["host"] == "smtp.example.com"
    assert sent["port"] == 587
    assert sent["login"] == ("smtp-user", "smtp-pass")
    assert sent["to"] == "owner@example.com"
    assert sent["from"] == "no-reply@example.com"
    assert sent["reply_to"] == "alice@example.com"


def test_analytics_logging_redacts_payload_values(caplog) -> None:
    payload = {
        "name": "page_view",
        "payload": {
            "email": "alice@example.com",
            "company": "Silico",
        },
    }

    with caplog.at_level("INFO", logger="silico.api"):
        response = client.post("/api/v1/analytics/event", json=payload)

    assert response.status_code == 200
    assert "page_view" in caplog.text
    assert "email" in caplog.text
    assert "company" in caplog.text
    assert "alice@example.com" not in caplog.text


def test_resolve_smiles_name_uses_pubchem_title(monkeypatch) -> None:
    class DummyAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> DummyResponse:
            if "/property/Title,IUPACName/JSON" in url:
                return DummyResponse(
                    200,
                    payload={
                        "PropertyTable": {
                            "Properties": [
                                {
                                    "Title": "ethanol",
                                    "IUPACName": "ethanol",
                                }
                            ]
                        }
                    },
                )
            return DummyResponse(404, payload={})

    monkeypatch.setattr("app.smiles_lookup.httpx.AsyncClient", DummyAsyncClient)

    response = client.post("/api/v1/chemistry/smiles/resolve-name", json={"smiles": "CCO"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolved_name"] == "ethanol"
    assert payload["source"] == "pubchem:title"


def test_resolve_smiles_name_falls_back_to_cactus(monkeypatch) -> None:
    class DummyAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> DummyResponse:
            if "pubchem.ncbi.nlm.nih.gov" in url:
                return DummyResponse(404, payload={})
            if "cactus.nci.nih.gov" in url:
                return DummyResponse(200, text="ethanol")
            return DummyResponse(404, payload={})

    monkeypatch.setattr("app.smiles_lookup.httpx.AsyncClient", DummyAsyncClient)

    response = client.post("/api/v1/chemistry/smiles/resolve-name", json={"smiles": "CCO"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["resolved_name"] == "ethanol"
    assert payload["source"] == "cactus:iupac"


def test_resolve_smiles_name_returns_404_when_unknown(monkeypatch) -> None:
    class DummyAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> DummyResponse:
            return DummyResponse(404, payload={})

    monkeypatch.setattr("app.smiles_lookup.httpx.AsyncClient", DummyAsyncClient)

    response = client.post("/api/v1/chemistry/smiles/resolve-name", json={"smiles": "not-smiles"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Molecule not found."


def test_resolve_smiles_name_returns_503_when_databases_fail(monkeypatch) -> None:
    class DummyAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, url: str) -> DummyResponse:
            if "pubchem.ncbi.nlm.nih.gov" in url:
                return DummyResponse(503, payload={})
            if "cactus.nci.nih.gov" in url:
                return DummyResponse(502, payload={})
            return DummyResponse(404, payload={})

    monkeypatch.setattr("app.smiles_lookup.httpx.AsyncClient", DummyAsyncClient)

    response = client.post("/api/v1/chemistry/smiles/resolve-name", json={"smiles": "CCO"})
    assert response.status_code == 503
    assert response.json()["detail"] == "Name lookup failed. Public databases did not respond."


def test_follow_up_chat_returns_grounded_method_summary_without_openai(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post(
        "/api/v1/agent/follow-up",
        json={
            "question": "Give me the experimental conditions of the best one please, very briefly",
            "request_text": "Quantification of Metformin in human plasma by HPLC-MS/MS for a bioequivalence study",
            "source_mode": "local_corpus",
            "runtime_mode": "live",
            "result_origin": "live_result",
            "system_summary": "Waters • C18 • 50 mm • 2.1 mm ID • 1.7 um • MS/MS",
            "search_query_used": "metformin plasma lc-ms/ms",
            "recommendations_count": 3,
            "active_recommendation": {
                "paper_id": "rec-1",
                "title": "Best current fit",
                "citation": "J. Chromatogr. A (2024)",
                "rationale": "Best overall balance of runtime and selectivity.",
                "core_method_summary": "Water / Acetonitrile • 10→70 %B gradient • 0.30 mL/min • 3.00 min runtime",
                "flow_rate_ml_min": 0.30,
                "run_time_min": 3.00,
                "column_temperature_c": 35.0,
                "is_scaled": True,
                "mobile_phase_a": {
                    "solvent": "Water",
                    "additive": "0.1% formic acid",
                    "ph_estimate": None,
                },
                "mobile_phase_b": {
                    "solvent": "Acetonitrile",
                    "additive": None,
                    "ph_estimate": None,
                },
                "gradient_profile": [
                    {"time_min": 0.0, "percent_b": 10.0},
                    {"time_min": 2.7, "percent_b": 70.0},
                    {"time_min": 2.71, "percent_b": 10.0},
                    {"time_min": 3.0, "percent_b": 10.0},
                ],
                "isocratic_percent_b": None,
                "trust_state": "review_backed",
                "validation_status": "valid",
                "warning_summary": [],
                "scaling_notes": ["Scaled to the current column geometry."],
                "dominant_differentiator": "Best selectivity fit.",
            },
            "history": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "grounded_fallback"
    assert "0.30 mL/min" in payload["answer"]
    assert "Acetonitrile" in payload["answer"]
    assert "10->70 %B" in payload["answer"]


def test_follow_up_chat_uses_openai_when_configured(monkeypatch) -> None:
    class DummyOpenAIResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": "Brief grounded answer from the model."
                        }
                    }
                ]
            }

    class DummyAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self) -> "DummyAsyncClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def post(self, url: str, headers: dict, json: dict) -> DummyOpenAIResponse:
            assert url == "https://api.openai.com/v1/chat/completions"
            assert headers["Authorization"] == "Bearer test-key"
            assert "Operator question" in json["messages"][1]["content"]
            return DummyOpenAIResponse()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("app.follow_up_chat.httpx.AsyncClient", DummyAsyncClient)

    response = client.post(
        "/api/v1/agent/follow-up",
        json={
            "question": "Why did this one win?",
            "request_text": "Quantification of Metformin in human plasma by HPLC-MS/MS for a bioequivalence study",
            "source_mode": "local_corpus",
            "runtime_mode": "live",
            "result_origin": "live_result",
            "system_summary": "Waters • C18 • 50 mm • 2.1 mm ID • 1.7 um • MS/MS",
            "search_query_used": "metformin plasma lc-ms/ms",
            "recommendations_count": 1,
            "active_recommendation": {
                "paper_id": "rec-1",
                "title": "Best current fit",
                "citation": "J. Chromatogr. A (2024)",
                "rationale": "Best overall balance of runtime and selectivity.",
                "core_method_summary": "Water / Acetonitrile • 10→70 %B gradient • 0.30 mL/min • 3.00 min runtime",
                "flow_rate_ml_min": 0.30,
                "run_time_min": 3.00,
                "column_temperature_c": 35.0,
                "is_scaled": True,
                "mobile_phase_a": {
                    "solvent": "Water",
                    "additive": "0.1% formic acid",
                    "ph_estimate": None,
                },
                "mobile_phase_b": {
                    "solvent": "Acetonitrile",
                    "additive": None,
                    "ph_estimate": None,
                },
                "gradient_profile": [],
                "isocratic_percent_b": 40.0,
                "trust_state": "review_backed",
                "validation_status": "valid",
                "warning_summary": [],
                "scaling_notes": [],
                "dominant_differentiator": "Best selectivity fit.",
            },
            "history": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "openai"
    assert payload["answer"] == "Brief grounded answer from the model."
