from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/ping", status_code=204)
async def root():
    return
