from fastapi import APIRouter

from app.api.deps import SettingsDep

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env.value}
