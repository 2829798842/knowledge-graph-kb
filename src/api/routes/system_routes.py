"""提供系统健康检查相关接口。
"""

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict[str, str]:
    """返回系统健康状态。

    Returns:
        dict[str, str]: 健康检查结果。
    """

    return {"status": "ok"}
