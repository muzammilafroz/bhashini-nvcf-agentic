import logging
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import pipeline

logger = logging.getLogger(__name__)

app = FastAPI(title="IndicTrans2 (Fallback) Server")

# Load the real model at startup!
# Using the fallback model from the skill since IndicTrans2 requires a gated HF login.
# This runs entirely on CPU.
logger.info("Loading Hugging Face model: Helsinki-NLP/opus-mt-en-hi...")
translator = pipeline("translation", model="Helsinki-NLP/opus-mt-en-hi", device="cpu")
logger.info("Model loaded successfully!")

class TranslateRequest(BaseModel):
    text: str
    src_lang: str
    tgt_lang: str

@app.post("/infer")
async def infer(req: TranslateRequest):
    """
    Real inference endpoint.
    """
    logger.info(f"Translating: {req.text} from {req.src_lang} to {req.tgt_lang}")
    
    # Run the real model
    result = translator(req.text)
    translated_text = result[0]['translation_text']
    
    return {"translation": translated_text}

@app.get("/health")
async def health():
    return {"status": "ok"}
