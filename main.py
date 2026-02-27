from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import container for dependency injection
from _bootstrap.bootstrap import Container

app = FastAPI(
    title="VirtuLingo",
    description="VirtuLingo - Language Mastery",
    version="1.0.0",
)

# Build container once
container = Container()

# Attach to app state
app.state.container = container

# Configure CORS for OAuth redirects and React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",  # Backend
        "http://localhost:5173",  # React dev server (Vite default)
        "http://localhost:5174",  # React dev server (alternative port)
        "http://localhost:3000",  # Alternative React dev port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api")
def root():
    return {
        "message": "VirtuLingo Backend is running",
    }
