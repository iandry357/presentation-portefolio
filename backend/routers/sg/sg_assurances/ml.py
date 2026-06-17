"""
Proxy ML — routes /sg/ml/* vers ML Service OVH port 8003.
"""
import os
import httpx
from fastapi import HTTPException, UploadFile

OVH_ML_HOST = os.getenv("OVH_ML_HOST", "51.68.130.23")
OVH_ML_PORT_SG = os.getenv("OVH_ML_PORT_SG", "8003")
ML_BASE_URL = f"http://{OVH_ML_HOST}:{OVH_ML_PORT_SG}"

TIMEOUT_DEFAULT = 30.0
TIMEOUT_QWEN    = 120.0


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


async def predict_ner(text: str) -> dict:
    return await _post("/predict/ner", {"text": text})


async def predict_qwen(prompt: str, max_new_tokens: int = 200) -> dict:
    return await _post(
        "/predict/qwen/finetuned",
        {"prompt": prompt, "max_new_tokens": max_new_tokens},
        timeout=TIMEOUT_QWEN,
    )


async def predict_yolo(file: UploadFile) -> dict:
    url = f"{ML_BASE_URL}/predict/yolo"
    try:
        content = await file.read()
        async with httpx.AsyncClient(timeout=TIMEOUT_DEFAULT) as client:
            resp = await client.post(
                url,
                files={"file": (file.filename, content, file.content_type)},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")