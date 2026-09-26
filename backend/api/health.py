from fastapi import APIRouter
from config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    settings = get_settings()
    ai_mode = "mock"
    if not settings.use_mock_ai:
        has_creds = bool(settings.watsonx_apikey and settings.watsonx_project_id)
        ai_mode = f"watsonx ({settings.watsonx_model_id})" if has_creds else "mock (fallback: credentials missing)"
    return {
        "status": "ok",
        "service": "ChangeGuard AI",
        "ai_mode": ai_mode,
    }
