import os
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.recommendation_context_optimizer import clear_recommendation_context_caches

os.environ.setdefault("TESTING", "true")
os.environ.setdefault("USE_MILVUS", "false")


@pytest.fixture(autouse=True)
def clear_recommendation_context_caches_between_tests():
    clear_recommendation_context_caches()
    yield
    clear_recommendation_context_caches()
