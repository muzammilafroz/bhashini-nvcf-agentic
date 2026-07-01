import logging
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import MarianMTModel, MarianTokenizer
import torch

logger = logging.getLogger(__name__)

app = FastAPI(title="IndicTrans2 (Fallback) Server")

model_name = "Helsinki-NLP/opus-mt-en-hi"
logger.info(f"Loading tokenizer and model: {model_name}...")
tokenizer = MarianTokenizer.from_pretrained(model_name)
model = MarianMTModel.from_pretrained(model_name)
logger.info("Model loaded successfully!")


class TranslateRequest(BaseModel):
    text: str = Field(..., max_length=5000, description="Text to translate (max 5000 chars)")
    src_lang: str = Field(..., max_length=20)
    tgt_lang: str = Field(..., max_length=20)


@app.post("/infer")
def infer(req: TranslateRequest):
    """
    Real inference endpoint.
    Uses a synchronous def so FastAPI runs it in a threadpool,
    preventing the CPU-bound model.generate() from blocking the event loop.
    """
    logger.info(f"Translating: {req.text[:80]}... from {req.src_lang} to {req.tgt_lang}")

    inputs = tokenizer(req.text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    with torch.no_grad():
        translated = model.generate(**inputs)
    translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)

    return {"translation": translated_text}


@app.get("/health")
async def health():
    return {"status": "ok"}
