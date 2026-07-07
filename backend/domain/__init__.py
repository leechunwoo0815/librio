# backend/domain/__init__.py
"""
领域层 — 按业务领域组织代码

架构意图：
  每个领域目录包含该领域完整的代码：
    - models.py: ORM 模型
    - schemas.py: Pydantic 请求/响应模型
    - repository.py: 数据访问层（继承 BaseRepository）
    - service.py: 业务逻辑
    - router.py: HTTP 端点
    - events.py: 领域事件定义（可选）

  为什么按领域分包？
  1. 新增需求永远是以领域为单位的（"加积分系统"），不是以层为单位的（"加一个 model"）
  2. 改一个功能只动一个文件夹，不会到处跳文件
  3. 领域边界强制开发者思考"这个逻辑属于哪个域"
  4. 未来如果需要拆微服务，每个 domain 就是天然的服务边界

领域清单：
  user/         用户域 — 微信登录、JWT 认证
  child/        孩子域 — 会员状态、阅读统计
  book/         图书域 — 图书信息 + 实体书副本(BookCopy)
  bookshelf/    书架域 — 想读清单 + 收藏夹（V3.1: 与借阅无关）
  borrow/       借阅域 — 线下借阅记录（V3.1 新增）
  deposit/      押金域 — 押金收取/退款/扣除（V3.1 新增）
  reservation/  预约域 — 预约借书/取书/过期（V3.1 新增）
  reading/      阅读域 — 阅读进度/打卡/音频伴读
  vocabulary/   词汇域 — 查词/生词本
  advancement/  晋级域 — 级别/测验/成就/证书
  order/        订单域 — 订单/支付
  refund/       退款域 — 退款申请/退款计算
  report/       报告域 — 观察期报告/学习报告
  certificate/  证书域 — 晋级证书
  profile/      名片域 — 个人阅读名片
  activity/     活动域 — 活动管理/报名
  admin/        管理域 — 后台管理（RBAC）
"""
