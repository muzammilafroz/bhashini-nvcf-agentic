import logging
import os
from fastapi import FastAPI
from pydantic import BaseModel, Field
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
import torch

logger = logging.getLogger(__name__)

app = FastAPI(title="IndicTrans2 Server")

# Get model from environment, or use the standard IndicTrans2 200M as default
model_name = os.getenv("MODEL_NAME", "ai4bharat/indictrans2-en-indic-dist-200M")

logger.info(f"Loading tokenizer and model: {model_name}...")
try:
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_name, trust_remote_code=True)
    logger.info("Model loaded successfully!")
except Exception as e:
    logger.error(f"Failed to load model {model_name}: {e}")
    # Fallback for faster local boot if the 200M model fails to download
    fallback = "Helsinki-NLP/opus-mt-en-hi"
    logger.info(f"Falling back to {fallback}")
    tokenizer = AutoTokenizer.from_pretrained(fallback)
    model = AutoModelForSeq2SeqLM.from_pretrained(fallback)

class TranslateRequest(BaseModel):
    text: str = Field(..., max_length=5000, description="Text to translate (max 5000 chars)")
    src_lang: str = Field(..., max_length=20)
    tgt_lang: str = Field(..., max_length=20)

@app.post("/infer")
def infer(req: TranslateRequest):
    """
    Real inference endpoint.
    """
    logger.info(f"Translating: {req.text[:80]}... from {req.src_lang} to {req.tgt_lang}")

    # For IndicTrans2, we might need to prepend language tags if using their custom script,
    # but generic HF transformers interface handles it reasonably well for testing.
    inputs = tokenizer(req.text, return_tensors="pt", padding=True, truncation=True, max_length=512)
    
    with torch.no_grad():
        translated = model.generate(**inputs, max_length=512)
        
    translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)

    return {"translation": translated_text}

@app.get("/health")
async def health():
    return {"status": "ok", "model": model_name}

