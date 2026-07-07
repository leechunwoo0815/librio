# backend/domain/profile/models.py
"""个人名片域 — 阅读名片（无独立模型，聚合 Child + Achievement 数据）

此域无独立 ORM 模型，ProfileService 直接查询 Child/Achievement/Level 等数据聚合生成。
保留 models.py 文件以保持领域结构一致性。
"""
