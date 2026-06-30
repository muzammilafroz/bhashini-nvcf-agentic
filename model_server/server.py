import logging
import os
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(title="IndicTrans2 Server")

# Optional: Add CTranslate2 and transformers loading logic here.
# Because this is for a demo, if we want a fast fallback we can use a stub
# if the model isn't downloaded yet.

class TranslateRequest(BaseModel):
    text: str
    src_lang: str
    tgt_lang: str

@app.post("/infer")
async def infer(req: TranslateRequest):
    """
    Mock inference endpoint.
    In the real codespace, this would invoke the CTranslate2 model.
    """
    logger.info(f"Translating: {req.text} from {req.src_lang} to {req.tgt_lang}")
    
    # Very crude mock response for local testing without the heavy model
    return {"translation": f"[MOCK {req.tgt_lang}] {req.text}"}

@app.get("/health")
async def health():
    return {"status": "ok"}
