from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from run_method_recommendation_cli import (
    _default_demo_paper_dir,
    _expand_paper_dir,
    _infer_require_ms_default,
)


def test_expand_paper_dir_collects_supported_files() -> None:
    paths = _expand_paper_dir(Path(__file__).resolve().parent / "paper_example")

    assert any(path.endswith(".pdf") for path in paths)
    assert any(path.endswith(".html") for path in paths)


def test_default_demo_paper_dir_exists() -> None:
    default_dir = _default_demo_paper_dir()

    assert default_dir is not None
    assert Path(default_dir).exists()


def test_infer_require_ms_default_from_request_text() -> None:
    assert _infer_require_ms_default("Recommend an LC-MS/MS method") is True
    assert _infer_require_ms_default("Recommend an HPLC method") is False
