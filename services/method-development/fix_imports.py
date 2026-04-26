import os

replacements = {
    "from .review_record_store import SqliteReviewRecordStore": "from .sqlite_review_record_store import SqliteReviewRecordStore",
    "from app.review_record_store import SqliteReviewRecordStore": "from app.sqlite_review_record_store import SqliteReviewRecordStore",
}

files = [
    "app/c12_orchestration.py",
    "app/c12_orchestration_router.py",
    "app/review_records_router.py",
    "tests/test_review_record_persistence.py",
    "tests/test_review_records_api.py",
    "tests/test_c12_orchestration_api.py",
    "tests/test_retrieval_api.py",
    "run_agent_eval_suite.py"
]

for file_path in files:
    with open(file_path, "r") as f:
        content = f.read()
    for k, v in replacements.items():
        content = content.replace(k, v)
    with open(file_path, "w") as f:
        f.write(content)
