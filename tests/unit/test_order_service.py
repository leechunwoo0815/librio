# tests/unit/test_order_service.py
"""
[What] 订单服务单元测试
[Why] TDD：先写失败测试
[How] 测试订单创建、支付等功能
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
from decimal import Decimal
from backend.services.order_service import OrderService
from backend.schemas.order import OrderCreate


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def order_service(mock_repo):
    return OrderService(mock_repo)


def test_create_parent_course_order(order_service, mock_repo):
    """
    [What] 测试创建亲子课程订单
    [Why] 验证订单创建逻辑
    [How] Mock仓库层，测试订单创建
    """
    order_data = OrderCreate(
        user_id=1,
        child_id=1,
        type=1,  # 亲子课程
        amount=99.00
    )

    mock_repo.create.return_value = MagicMock(
        id=1,
        order_no="MW20260604001",
        user_id=1,
        child_id=1,
        type=1,
        amount=Decimal("99.00"),
        status="pending",
        payment_no=None,
        payment_time=None,
        remark=None,
        create_time=datetime.now()
    )

    result = order_service.create_order(order_data)

    assert result.id == 1
    assert result.order_no.startswith("MW")


def test_create_observation_order(order_service, mock_repo):
    """
    [What] 测试创建观察力训练订单
    [Why] 验证不同类型订单创建
    [How] Mock仓库层，测试观察力训练订单
    """
    order_data = OrderCreate(
        user_id=1,
        child_id=1,
        type=2,  # 观察力训练
        amount=199.00
    )

    mock_repo.create.return_value = MagicMock(
        id=2,
        order_no="MW20260604002",
        user_id=1,
        child_id=1,
        type=2,
        amount=Decimal("199.00"),
        status="pending",
        payment_no=None,
        payment_time=None,
        remark=None,
        create_time=datetime.now()
    )

    result = order_service.create_order(order_data)

    assert result.id == 2
    assert result.order_no.startswith("MW")


def test_create_member_order(order_service, mock_repo):
    """
    [What] 测试创建正式会员订单
    [Why] 验证会员订单创建
    [How] Mock仓库层，测试会员订单
    """
    order_data = OrderCreate(
        user_id=1,
        child_id=1,
        type=3,  # 正式会员
        amount=999.00
    )

    mock_repo.create.return_value = MagicMock(
        id=3,
        order_no="MW20260604003",
        user_id=1,
        child_id=1,
        type=3,
        amount=Decimal("999.00"),
        status="pending",
        payment_no=None,
        payment_time=None,
        remark=None,
        create_time=datetime.now()
    )

    result = order_service.create_order(order_data)

    assert result.id == 3
    assert result.order_no.startswith("MW")


def test_create_deposit_order(order_service, mock_repo):
    """
    [What] 测试创建押金订单
    [Why] 验证押金订单创建
    [How] Mock仓库层，测试押金订单
    """
    order_data = OrderCreate(
        user_id=1,
        child_id=1,
        type=4,  # 押金
        amount=200.00
    )

    mock_repo.create.return_value = MagicMock(
        id=4,
        order_no="MW20260604004",
        user_id=1,
        child_id=1,
        type=4,
        amount=Decimal("200.00"),
        status="pending",
        payment_no=None,
        payment_time=None,
        remark=None,
        create_time=datetime.now()
    )

    result = order_service.create_order(order_data)

    assert result.id == 4
    assert result.order_no.startswith("MW")


def test_get_order_by_id(order_service, mock_repo):
    """
    [What] 测试根据ID获取订单
    [Why] 验证订单查询逻辑
    [How] Mock仓库层，测试订单查询
    """
    mock_repo.get_by_id.return_value = MagicMock(
        id=1,
        order_no="MW20260604001",
        user_id=1,
        child_id=1,
        type=1,
        amount=Decimal("99.00"),
        status="pending",
        payment_no=None,
        payment_time=None,
        remark=None,
        create_time=datetime.now()
    )

    result = order_service.get_order_by_id(1)

    assert result is not None
    assert result.id == 1


def test_get_order_not_found(order_service, mock_repo):
    """
    [What] 测试订单不存在的情况
    [Why] 验证订单查询的空值处理
    [How] Mock仓库层返回None
    """
    mock_repo.get_by_id.return_value = None

    result = order_service.get_order_by_id(999)

    assert result is None


def test_get_user_orders(order_service, mock_repo):
    """
    [What] 测试获取用户订单列表
    [Why] 验证用户订单查询
    [How] Mock仓库层，测试订单列表查询
    """
    mock_repo.get_by_user_id.return_value = [
        MagicMock(
            id=1,
            order_no="MW20260604001",
            user_id=1,
            child_id=1,
            type=1,
            amount=Decimal("99.00"),
            status="pending",
            payment_no=None,
            payment_time=None,
            remark=None,
            create_time=datetime.now()
        ),
        MagicMock(
            id=2,
            order_no="MW20260604002",
            user_id=1,
            child_id=1,
            type=2,
            amount=Decimal("199.00"),
            status="paid",
            payment_no="PAY123",
            payment_time=datetime.now(),
            remark=None,
            create_time=datetime.now()
        ),
    ]

    result = order_service.get_user_orders(1)

    assert len(result) == 2
    mock_repo.get_by_user_id.assert_called_once_with(1)


def test_update_order_status(order_service, mock_repo):
    """
    [What] 测试更新订单状态
    [Why] 验证订单状态更新逻辑
    [How] Mock仓库层，测试状态更新
    """
    mock_order = MagicMock(
        id=1,
        order_no="MW20260604001",
        user_id=1,
        child_id=1,
        type=1,
        amount=Decimal("99.00"),
        status="pending",
        payment_no=None,
        payment_time=None,
        remark=None,
        create_time=datetime.now()
    )
    mock_repo.get_by_id.return_value = mock_order
    mock_repo.update.return_value = mock_order

    result = order_service.update_order_status(1, "paid")

    assert result is not None
    mock_repo.update.assert_called_once()


def test_order_no_generation(order_service):
    """
    [What] 测试订单号生成
    [Why] 验证订单号格式正确
    [How] 测试订单号生成函数
    """
    order_no = order_service.generate_order_no()

    assert order_no.startswith("MW")
    assert len(order_no) == 15  # MW + 8位日期 + 5位序号
