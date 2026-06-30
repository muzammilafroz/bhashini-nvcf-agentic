import logging
from fastapi import FastAPI
from pydantic import BaseModel
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
    inputs = tokenizer(req.text, return_tensors="pt", padding=True)
    with torch.no_grad():
        translated = model.generate(**inputs)
    translated_text = tokenizer.decode(translated[0], skip_special_tokens=True)
    
    return {"translation": translated_text}

@app.get("/health")
async def health():
    return {"status": "ok"}
