import asyncio

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.common.dependencies import get_wechat_service
from backend.domain.user.models import User
from backend.domain.wechat.service import WeChatService
from backend.middleware.auth import get_current_user

router = APIRouter(prefix="/security", tags=["安全"])


class CheckTextRequest(BaseModel):
    content: str


class CheckTextResponse(BaseModel):
    passed: bool
    message: str


@router.post("/check-text", response_model=CheckTextResponse)
async def check_text(
    request: CheckTextRequest,
    wechat_service: WeChatService = Depends(get_wechat_service),
    current_user: User = Depends(get_current_user),
):
    try:
        access_token = await asyncio.to_thread(wechat_service.get_access_token)
    except Exception:
        return CheckTextResponse(passed=False, message="安全检查暂时不可用，请稍后重试")

    url = "https://api.weixin.qq.com/wxa/msg_sec_check"
    async with httpx.AsyncClient(timeout=3) as client:
        resp = await client.post(
            url,
            params={"access_token": access_token},
            json={
                "content": request.content,
                "version": 2,
                "scene": 1,
            },
        )
        result = resp.json()

    errcode = result.get("errcode", 0)
    if errcode == 87014:
        return CheckTextResponse(passed=False, message="内容包含违规信息，请修改后重试")
    if errcode != 0:
        return CheckTextResponse(passed=False, message="安全检查暂时不可用，请稍后重试")

    return CheckTextResponse(passed=True, message="")
