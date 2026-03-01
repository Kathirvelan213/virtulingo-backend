from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import time

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


# Debug middleware to log all requests
class DebugMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        print(f"\n[Middleware] Incoming request: {request.method} {request.url.path}")
        print(f"[Middleware] Headers: {dict(request.headers)}")
        print(f"[Middleware] Scope type: {request.scope.get('type')}")
        
        try:
            response = await call_next(request)
            print(f"[Middleware] Response status: {response.status_code}")
            return response
        except Exception as e:
            print(f"[Middleware] ERROR: {e}")
            import traceback
            traceback.print_exc()
            raise


app.add_middleware(DebugMiddleware)

# CORS — allow Unity WebGL builds and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:5173",
        "http://localhost:3000",
        "*",  # Allow all origins for WebSocket testing
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
