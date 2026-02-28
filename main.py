from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from _bootstrap.bootstrap import Container
from api.api import api_router

app = FastAPI(
    title="VirtuLingo",
    description="VirtuLingo — Real-time AI-powered Language Learning Backend",
    version="1.0.0",
)

# Build and attach the DI container once at startup
container = Container()
app.state.container = container

# CORS — allow Unity WebGL builds and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routes
app.include_router(api_router)


@app.get("/health")
def healthcheck():
    return {"status": "ok", "service": "virtulingo-backend"}
