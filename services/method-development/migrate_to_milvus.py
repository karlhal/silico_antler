from __future__ import annotations

import os
from pathlib import Path
from app.retrieval_store import load_seed_method_records
from app.milvus_retrieval_store import MilvusRetrievalStore
from app.retrieval_schemas import RetrievalRecordReviewSummary

def migrate():
    db_path = os.environ.get("MILVUS_DB_PATH", "silico_retrieval.db")
    print(f"Migrating to Milvus at {db_path}...")
    
    store = MilvusRetrievalStore(db_path)
    records = load_seed_method_records()
    print(f"Loaded {len(records)} base records.")
    
    for record in records:
        review_summary = RetrievalRecordReviewSummary(
            record_state="seeded",
            validation_status=record.validation.status,
            retrieval_ready=record.validation.retrieval_ready,
        )
        store.upsert_record(record, review_summary)
        print(f"Inserted record: {record.record_id}")
        
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
