from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health")
def health():
    return {
        "status": "healthy",
        "server": "IX Endpoint Server",
        "version": "1.0.0"
    }
