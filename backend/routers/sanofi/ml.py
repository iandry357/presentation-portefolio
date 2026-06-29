import os

import httpx
from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

class GraphRagRequest(BaseModel):
    cluster_id: int
    question: str

router = APIRouter()

OVH_ML_HOST = os.getenv("OVH_ML_HOST", "51.68.130.23")
OVH_ML_PORT = os.getenv("OVH_ML_PORT", "8001")
ML_BASE_URL = f"http://{OVH_ML_HOST}:{OVH_ML_PORT}"


async def _get(path: str) -> dict:
    url = f"{ML_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")


@router.get("/sanofi/ml/clustering")
async def get_clustering():
    return await _get("/ml/clustering")


@router.get("/sanofi/ml/forecasting")
async def get_forecasting():
    return await _get("/ml/forecasting")

@router.get("/sanofi/ml/topic-modeling")
async def get_topic_modeling():
    return await _get("/ml/topic-modeling")

@router.get("/sanofi/ml/therapeutic-insight")
async def get_therapeutic_insight():
    return await _get("/ml/therapeutic-insight")

async def post_graph_rag(payload: GraphRagRequest) -> dict:
    url = f"{ML_BASE_URL}/ml/graph-rag"
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload.model_dump())
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")