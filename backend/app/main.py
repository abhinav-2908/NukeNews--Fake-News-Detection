from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.database.db import init_db
from app.core.config import settings

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield

app=FastAPI(title="NukeNews API",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in settings.frontend_origins.split(',') if x.strip()],allow_credentials=False,allow_methods=['GET','POST','DELETE'],allow_headers=['Content-Type'])
app.include_router(router)
