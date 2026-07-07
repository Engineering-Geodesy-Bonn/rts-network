from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get(
    "/ping",
    status_code=204,
    summary="Health check endpoint.",
    response_description="No content.",
    responses={
        204: {"description": "Service is healthy."},
    },
)
async def root():
    return
