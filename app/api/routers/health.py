from fastapi import APIRouter

from app.api.deps import RuntimeSettingsDep

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health")
async def health(runtime: RuntimeSettingsDep) -> dict[str, str]:
    return {"status": "ok", "env": runtime.app_env}
