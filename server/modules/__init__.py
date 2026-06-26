"""Business logic for the EGI server. Routes in ``routes/`` are thin HTTP
adapters that call these functions; logic here takes Pydantic models / params
and returns dicts or models (no FastAPI types except HTTPException for errors)."""
