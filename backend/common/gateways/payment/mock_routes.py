# backend/common/gateways/payment/mock_routes.py
"""Mock 支付辅助路由 — 仅在 MOCK_PAYMENT=true 时注册

提供测试用支付/退款回调模拟入口，直接调用业务层回调处理链路，
确保状态机、事务、幂等校验全部生效。
"""

import json
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.domain.admin.models import Admin
from backend.middleware.admin_auth import get_current_admin
from backend.middleware.admin_rbac import require_perm

logger = logging.getLogger(__name__)

mock_payment_router = APIRouter(prefix="/mock/payment", tags=["Mock-支付"])


@mock_payment_router.post(
    "/notify/order", dependencies=[Depends(require_perm("order.edit"))]
)
async def mock_payment_notify(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    """模拟支付成功回调 — 直接调用业务层 handle_payment_callback"""
    from backend.domain.order.schemas import OrderPayCallback
    from backend.domain.order.service import OrderService
    from backend.database import get_session

    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        data = {}

    out_trade_no = data.get("out_trade_no", "")
    if not out_trade_no:
        raise HTTPException(400, "缺少 out_trade_no")

    db = get_session()()
    try:
        svc = OrderService(db)
        callback = OrderPayCallback(
            order_no=out_trade_no,
            trade_no=data.get("transaction_id", f"mock_txn_{out_trade_no[-8:]}"),
            pay_type=1,
            amount=Decimal(str(data.get("amount", 0))),
        )
        result = svc.handle_payment_callback(callback)
        db.commit()

        logger.info(
            "[MockPayNotify] 支付回调模拟成功 out_trade_no=%s admin_id=%s",
            out_trade_no,
            admin.id,
        )
        return {
            "success": True,
            "order": {"id": result.id, "pay_status": result.pay_status},
        }
    except Exception as e:
        db.rollback()
        logger.error("[MockPayNotify] 支付回调失败: %s", e)
        raise HTTPException(500, str(e))
    finally:
        db.close()


@mock_payment_router.post(
    "/notify/refund", dependencies=[Depends(require_perm("order.edit"))]
)
async def mock_refund_notify(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    """模拟退款成功回调"""
    from backend.domain.refund.service import RefundService
    from backend.database import get_session

    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        data = {}

    order_no = data.get("order_no", "")
    if not order_no:
        raise HTTPException(400, "缺少 order_no")

    db = get_session()()
    try:
        svc = RefundService(db)
        svc.mark_refunded(order_no)
        db.commit()

        logger.info(
            "[MockRefundNotify] 退款回调模拟成功 order_no=%s admin_id=%s",
            order_no,
            admin.id,
        )
        return {"success": True, "order_no": order_no}
    except Exception as e:
        db.rollback()
        logger.error("[MockRefundNotify] 退款回调失败: %s", e)
        raise HTTPException(500, str(e))
    finally:
        db.close()


@mock_payment_router.post(
    "/notify/deposit", dependencies=[Depends(require_perm("deposit.pay"))]
)
async def mock_deposit_notify(
    request: Request,
    admin: Admin = Depends(get_current_admin),
):
    """模拟押金支付回调 — PENDING → PAID"""
    from backend.domain.deposit.service import DepositService
    from backend.database import get_session

    try:
        body = await request.body()
        data = json.loads(body) if body else {}
    except json.JSONDecodeError:
        data = {}

    order_no = data.get("order_no", "")
    if not order_no:
        raise HTTPException(400, "缺少 order_no")

    db = get_session()()
    try:
        svc = DepositService(db)
        result = svc.handle_callback(order_no)
        db.commit()

        logger.info(
            "[MockDepositNotify] 押金回调模拟成功 order_no=%s admin_id=%s",
            order_no,
            admin.id,
        )
        return {"success": True, "deposit": {"id": result.id, "status": result.status}}
    except Exception as e:
        db.rollback()
        logger.error("[MockDepositNotify] 押金回调失败: %s", e)
        raise HTTPException(500, str(e))
    finally:
        db.close()
