"""
Proxy ML — routes /banque-de-france/ml/* vers ML Service OVH port 8007.
"""
import os
import httpx
from fastapi import HTTPException

OVH_ML_HOST        = os.getenv("OVH_ML_HOST", "51.68.130.23")
OVH_ML_PORT_BANQUE = os.getenv("OVH_ML_PORT_BANQUE", "8007")
ML_BASE_URL         = f"http://{OVH_ML_HOST}:{OVH_ML_PORT_BANQUE}"

TIMEOUT_DEFAULT = 120.0


async def _get(path: str, timeout: float = TIMEOUT_DEFAULT) -> dict:
    url = f"{ML_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")


async def _post(path: str, payload: dict, timeout: float = TIMEOUT_DEFAULT) -> dict:
    url = f"{ML_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")


async def get_topic_modeling() -> dict:
    return await _get("/predict/topic-modeling")


async def get_eba_scores() -> dict:
    return await _get("/predict/eba")


async def predict_classification(text: str) -> dict:
    return await _post("/predict/classification", {"text": text})

async def get_classification_examples() -> dict:
    return await _get("/predict/classification/examples")