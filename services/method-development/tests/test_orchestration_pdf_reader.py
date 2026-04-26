from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ai_runtime_settings import AiRuntimeSettings
from app.gemini_orchestration_client import OpenRouterOrchestrationClient


def test_openrouter_pdf_reader_uses_cloudflare_file_parser(monkeypatch) -> None:
    captured_payloads: list[dict] = []

    class _FakeResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"mobile_phase_a":{"solvent":"water","additive":"0.1% formic acid"},'
                                '"mobile_phase_b":{"solvent":"acetonitrile","additive":"0.1% formic acid"},'
                                '"flow_rate_ml_min":0.35}'
                            )
                        }
                    }
                ]
            }

    class _FakeHttpxClient:
        def __init__(self, *, timeout: int) -> None:
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def post(self, _url: str, *, headers: dict, json: dict):
            assert headers["Authorization"] == "Bearer or-test-key"
            captured_payloads.append(json)
            return _FakeResponse()

    monkeypatch.setattr("app.gemini_orchestration_client.httpx.Client", _FakeHttpxClient)
    client = OpenRouterOrchestrationClient(
        AiRuntimeSettings(
            llm_provider="openrouter",
            openrouter_api_key="or-test-key",
            worker_model="google/gemma-4-31b-it:free",
            planner_model="google/gemma-4-31b-it:free",
        )
    )

    payload = client.extract_hplc_parameters_from_pdf(
        pdf_bytes=b"%PDF-1.7\n%%EOF",
        filename="method.pdf",
        pdf_url="https://example.test/method.pdf",
        request_text="Find metformin in plasma.",
        title="Method paper",
    )

    assert payload is not None
    assert payload["flow_rate_ml_min"] == 0.35
    request_payload = captured_payloads[0]
    assert request_payload["plugins"] == [
        {"id": "file-parser", "pdf": {"engine": "cloudflare-ai"}}
    ]
    user_content = request_payload["messages"][0]["content"]
    assert user_content[1]["type"] == "file"
    assert user_content[1]["file"]["filename"] == "method.pdf"
    assert user_content[1]["file"]["file_data"] == "https://example.test/method.pdf"
    assert "response_format" not in request_payload
