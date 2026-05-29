import uvicorn
from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router, initiate_outbound_call
from app.config.src import SERVER_HOST, SERVER_PORT

app = FastAPI(title="Collections Voice Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the API router for Twilio webhook paths
app.include_router(api_router, prefix="/api")

# Root-level -> orchestration layer '/call' directly
@app.post("/call")
async def call_root(request: Dict[str, Any]):
    """Root-level alias for /api/call — allows orchestration layer to POST to /call directly."""
    return await initiate_outbound_call(request)

if __name__ == "__main__":
    print(f"Starting server at http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)