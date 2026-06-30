---
name: indictrans2-cpu-serving
description: Serve a tiny real BHASHINI-family translation model (IndicTrans2 distilled 200M) on CPU for free using CTranslate2 int8, wrapped in FastAPI, containerized, and hosted on a Hugging Face Space. Use in Phase 3 or whenever building the model "function under test". The heavy steps (conversion, inference, docker build) run on a Codespace, NOT the local Windows laptop.
---

# Serve IndicTrans2-dist-200M on CPU, free

This is the ONE part of the project that is CPU-heavy and Linux-only. **Do the conversion,
inference, and Docker build on a GitHub Codespace.** You can still edit `server.py` /
`Dockerfile` locally with Claude Code; just run/build them in the Codespace.

Model: `ai4bharat/indictrans2-en-indic-dist-200M` (Hugging Face, **MIT**, ~200M params,
gated -> log in / accept terms to download). Indic->En variant:
`ai4bharat/indictrans2-indic-en-dist-200M`.

## Fast CPU path = CTranslate2 int8
- The official repo https://github.com/AI4Bharat/IndicTrans2 ships each checkpoint as a
  fairseq dir **plus 2 pre-converted CTranslate2 dirs**. Use the CT2 dir with int8.
- ~200-250 MB weights at int8; fits a 2-vCPU / 16 GB box; expect a few hundred ms to ~1 s
  per short sentence with small beam (`beam_size=1..5`).
- If converting a fairseq ckpt yourself:
  `ct2-fairseq-converter --model_path <ckpt> --data_dir <bin> --quantization int8 --user_dir <IT2 arch> --output_dir <out>`
- Benchmark `int8` vs `int8_float32` — naive int8 can drop a few BLEU.

## Gotchas (write these into the README)
- **`IndicTransToolkit` is Linux/macOS only.** Never run it on native Windows -> this is the
  reason model work happens in the Codespace. (CTranslate2 itself is cross-platform, but
  keep all model work in one place to avoid surprises.)
- Language codes are **FLORES**: `eng_Latn`, `hin_Deva`, `tam_Taml`, ...
- Preprocess/postprocess with `IndicProcessor` (script normalization + lang tags). On the
  HF path always pass `trust_remote_code=True`; drop flash-attn/float16 on CPU.

## Server shape (FastAPI)
- `POST /infer  { "text": "...", "src_lang": "eng_Latn", "tgt_lang": "hin_Deva" }` -> `{ "translation": "..." }`
- `GET /health -> 200 {"status":"ok"}`  (the mock/router poll this)
- Use the repo wrapper: `Model(ckpt_dir, model_type="ctranslate2").batch_translate(...)`.

## Docker + hosting
- CPU base `python:3.11-slim`; `pip install ctranslate2 transformers sentencepiece fastapi uvicorn`.
- Build/run the image in the Codespace (`docker build`, `docker run -p 8000:8000`).
- Host as a **Hugging Face Space (Docker SDK, free CPU 2 vCPU/16 GB)**. Push needs `HF_TOKEN`
  (write). Free Spaces **sleep when idle** -> first request after sleep is a slow cold start
  (fine for a demo, note it). Limited persistence — treat as stateless.
- The Space's public URL is the "deployed function" the router points at.

## Fallback model
`Helsinki-NLP/opus-mt-en-hi` (smaller/faster, one pair) if the 200M feels heavy.

## Done when
`curl <url>/infer -d '{"text":"hello","src_lang":"eng_Latn","tgt_lang":"hin_Deva"}'`
returns Hindi in ~1 s and `/health` is green.
