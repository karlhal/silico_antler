import os

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

    # Fix improper single-line imports
    content = content.replace(
        "from .sqlite_review_record_store import SqliteReviewRecordStore, ReviewRecordStatusError",
        "from .sqlite_review_record_store import SqliteReviewRecordStore\nfrom .review_record_store import ReviewRecordStatusError"
    )

    # Fix improper imports in test_review_records_api.py etc
    content = content.replace(
        "from app.sqlite_review_record_store import SqliteReviewRecordStore, ReviewRecordStatusError",
        "from app.sqlite_review_record_store import SqliteReviewRecordStore\nfrom app.review_record_store import ReviewRecordStatusError"
    )

    # For review_records_router.py
    content = content.replace(
        "from .sqlite_review_record_store import (\n    SqliteReviewRecordStore,\n    ReviewRecordNotFoundError,\n    ReviewRecordStatusError,\n)",
        "from .sqlite_review_record_store import SqliteReviewRecordStore\nfrom .review_record_store import ReviewRecordNotFoundError, ReviewRecordStatusError"
    )
    content = content.replace(
        "from .review_record_store import (\n    SqliteReviewRecordStore,\n    ReviewRecordNotFoundError,\n    ReviewRecordStatusError,\n)",
        "from .sqlite_review_record_store import SqliteReviewRecordStore\nfrom .review_record_store import ReviewRecordNotFoundError, ReviewRecordStatusError"
    )
    
    with open(file_path, "w") as f:
        f.write(content)

# Also remove the bottom line from review_record_store.py
with open("app/review_record_store.py", "r") as f:
    lines = f.readlines()
with open("app/review_record_store.py", "w") as f:
    for line in lines:
        if "from .sqlite_review_record_store import SqliteReviewRecordStore" not in line:
            f.write(line)

