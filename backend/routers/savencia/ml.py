import os

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File

router = APIRouter()

OVH_ML_HOST = os.getenv("OVH_ML_HOST", "51.68.130.23")
OVH_ML_PORT_SAVENCIA = os.getenv("OVH_ML_PORT_SAVENCIA", "8002")
ML_BASE_URL = f"http://{OVH_ML_HOST}:{OVH_ML_PORT_SAVENCIA}"


async def _get(path: str) -> dict:
    url = f"{ML_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")


async def _post_image(path: str, image_bytes: bytes, content_type: str) -> dict:
    url = f"{ML_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                files={"file": ("image", image_bytes, content_type)},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timeout")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="ML service error")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service unreachable")


async def get_topic_modeling() -> dict:
    return await _get("/ml/topic-modeling")


async def vit_inference(image_bytes: bytes, content_type: str) -> dict:
    return await _post_image("/ml/vit-inference", image_bytes, content_type)