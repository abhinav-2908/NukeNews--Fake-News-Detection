import json, uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from app.schemas.analysis import TextRequest
from app.services.analyzer import analyze
from app.extraction.url import extract_url
from app.extraction.files import pdf_text,image_text
from app.database.db import SessionLocal, Analysis
from app.core.config import settings

router=APIRouter(prefix="/api")
@router.get('/health')
def health(): return {"status":"ok","service":"NukeNews"}
@router.get('/models')
def models():
 from app.ml.inference import classifier
 return {"classifier":"ready" if classifier.pipeline is not None else "not_trained","llm":"configured" if settings.openrouter_api_key and settings.openrouter_model else "not_configured","search_provider":settings.search_provider}
@router.get('/metrics')
def metrics():
 p=(Path(__file__).resolve().parents[3]/settings.metrics_path).resolve()
 return json.loads(p.read_text()) if p.exists() else {"status":"not_available","message":"No evaluation results exist. Train with the real ISOT dataset first."}
def save(result):
 with SessionLocal() as db:
  payload=result.model_dump(mode="json"); db.add(Analysis(id=result.id, input_type=result.input_type, verdict=result.verdict,title=result.title,payload=payload)); db.commit()
 return result
@router.post('/analyze/text')
async def text(req:TextRequest):
 try:return save(await analyze(req.text,req.title,req.input_type,req.extraction))
 except ValueError as e: raise HTTPException(422,str(e))
@router.post('/analyze/url')
async def url(req:dict):
 target=req.get('url','')
 try:
  extracted=await extract_url(target); return save(await analyze(extracted['text'],extracted['title'],'url',extracted))
 except ValueError as e: raise HTTPException(422,str(e))
 except Exception as e: raise HTTPException(400,f"URL extraction failed: {e}")
async def extract_upload(file:UploadFile,kind:str):
 data=await file.read(settings.max_upload_mb*1024*1024+1)
 if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"Upload exceeds the configured 15 MB limit.")
 if kind=='pdf':
  if not data.startswith(b'%PDF-'): raise HTTPException(415,"File content is not a PDF.")
  try: content,pages=pdf_text(data)
  except Exception as e: raise HTTPException(422,str(e))
  if not content.strip(): raise HTTPException(422,"PDF contains no extractable text. Check whether OCR dependencies and language packs are installed.")
  meta={"filename":file.filename,"pages":pages,"status":"extracted"}
 else:
  try: content=image_text(data)
  except Exception as e: raise HTTPException(422,str(e))
  if not content: raise HTTPException(422,"No text was recognized in this image.")
  meta={"filename":file.filename,"status":"ocr_complete"}
 return {"text":content,"extraction":meta}
@router.post('/extract/pdf')
async def extract_pdf(file:UploadFile=File(...)): return await extract_upload(file,'pdf')
@router.post('/extract/image')
async def extract_image(file:UploadFile=File(...)): return await extract_upload(file,'image')
@router.post('/analyze/pdf')
async def pdf(file:UploadFile=File(...)):
 extracted=await extract_upload(file,'pdf'); return save(await analyze(extracted['text'],"",'pdf',extracted['extraction']))
@router.post('/analyze/image')
async def image(file:UploadFile=File(...)):
 extracted=await extract_upload(file,'image'); return save(await analyze(extracted['text'],"",'image',extracted['extraction']))
@router.get('/history')
def history(verdict:str|None=Query(default=None),limit:int=Query(default=50,le=100)):
 with SessionLocal() as db:
  q=db.query(Analysis)
  if verdict:q=q.filter(Analysis.verdict==verdict)
  return [r.payload for r in q.order_by(Analysis.created_at.desc()).limit(limit).all()]
@router.get('/history/{analysis_id}')
def get_history(analysis_id:str):
 with SessionLocal() as db:
  r=db.get(Analysis,analysis_id)
  if not r: raise HTTPException(404,"Analysis not found")
  return r.payload
@router.delete('/history/{analysis_id}')
def delete_history(analysis_id:str):
 with SessionLocal() as db:
  r=db.get(Analysis,analysis_id)
  if not r: raise HTTPException(404,"Analysis not found")
  db.delete(r); db.commit(); return {"deleted":True}

@router.delete('/history')
def clear_history():
 with SessionLocal() as db:
  count=db.query(Analysis).delete(); db.commit(); return {"deleted_count":count}
