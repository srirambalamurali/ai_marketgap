from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/collect", tags=["collect"])


class CollectRequest(BaseModel):
    query: str


class CollectResponse(BaseModel):
    query: str
    documents: list[dict] = []


@router.post("", response_model=CollectResponse)
async def collect_data(request: CollectRequest):
    """Collect market data for the given query. (Phase 1 placeholder)"""
    return CollectResponse(query=request.query, documents=[])
