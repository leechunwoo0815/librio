"""WeChat API routes — QR code generation"""

import asyncio
import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response

from backend.common.dependencies import get_wechat_service
from backend.domain.wechat.service import WeChatAPIError
from backend.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wechat", tags=["微信"])


@router.get("/qr-code")
async def get_qr_code(
    scene: str = Query(..., min_length=1, max_length=32, description="场景值"),
    page: str = Query(..., min_length=1, max_length=256, description="页面路径"),
    service=Depends(get_wechat_service),
    current_user=Depends(get_current_user),
):
    """生成微信小程序码（无限制数量）

    为证书分享、学习报告分享等场景提供小程序码图片。
    复用后端 access_token 缓存，避免前端直接调用微信API。

    用法:
        GET /wechat/qr-code?scene=cert_123&page=pages/member-pkg/certificate/certificate
        → 200 image/png
    """
    try:
        png = await asyncio.to_thread(service.get_unlimited_qr_code, scene, page)
    except WeChatAPIError as e:
        logger.warning("微信 API 调用失败: %s", e)
        return JSONResponse(status_code=502, content={"detail": str(e)})

    return Response(
        content=png,
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )
