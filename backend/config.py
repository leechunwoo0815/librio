# backend/config.py
"""
[What] 项目配置文件
[Why] 集中管理所有配置项，便于维护
[How] 使用pydantic-settings从环境变量读取配置
"""

import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    [What] 项目配置类
    [Why] 使用pydantic-settings自动验证配置类型
    [How] 继承BaseSettings，定义配置字段
    """

    # 应用配置
    APP_NAME: str = "DmkWords API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    ENABLE_TEST_TOKEN: bool = False

    # Mock 网关开关（仅本地开发使用，生产环境必须关闭）
    MOCK_PAYMENT: bool = False  # 支付 Mock 网关（默认关闭，生产安全）
    MOCK_SMS: bool = (
        False  # 短信 Mock 网关（生产必须关闭——真实 SDK 未接入时本地开发手动设为 True）
    )

    # 生产短信服务商配置
    SMS_PROVIDER: str = "mock"  # mock / tencent / aliyun
    SMS_APP_ID: str = ""  # SDK AppID
    SMS_APP_KEY: str = ""  # SDK AppKey / AccessKeySecret
    SMS_SIGN_NAME: str = "DmkWords"  # 短信签名（需平台审核通过）
    SMS_TEMPLATE_CODE: str = ""  # 验证码模板 ID

    # 数据库配置
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "dmkwords"

    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    # Redis 宕机时分布式锁的降级策略：True=无锁执行（单实例/开发可接受）；
    # False=跳过任务（多实例生产必须，防多实例并发重复执行）。审查 P1-3
    REDIS_LOCK_FAIL_OPEN: bool = True

    # JWT配置 - 通过环境变量 SECRET_KEY 覆盖（pydantic-settings 自动读取）
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 2  # 2小时
    ADMIN_TOKEN_EXPIRE_HOURS: int = 8  # 管理员 Token 过期时间（小时）

    # 微信配置
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    WECHAT_MCH_ID: str = ""
    WECHAT_API_KEY: str = ""

    # 微信支付 V3 配置
    WECHAT_API_KEY_V3: str = ""  # V3 专用 API 密钥
    WECHAT_CERT_SERIAL_NO: str = ""  # 商户证书序列号
    WECHAT_PRIVATE_KEY_PATH: str = ""  # 商户私钥 PEM 文件路径
    WECHAT_PLATFORM_CERT_PATH: str = ""  # 微信平台证书 PEM 文件路径
    WECHAT_PAY_NOTIFY_URL: str = ""  # 支付回调通知 URL
    WECHAT_REFUND_NOTIFY_URL: str = ""  # 微信退款结果通知 URL（F55）
    WECHAT_SUBSCRIBE_ENABLED: bool = (
        False  # 订阅消息推送总开关（生产填好模板 ID 后设为 True，防误发）
    )

    # 服务器配置
    SERVER_HOST: str = ""
    SERVER_PORT: int = 8002

    # 端口配置
    BACKEND_PORT: int = 8002
    FRONTEND_PORT: int = 3002

    @property
    def DATABASE_URL(self) -> str:
        """
        [What] 获取数据库连接URL
        [Why] SQLAlchemy需要完整的连接字符串
        [How] 优先使用 DATABASE_URL 环境变量（CI 用 SQLite）；否则拼接 MySQL 参数
        """
        env_url = os.environ.get("DATABASE_URL")
        if env_url:
            return env_url
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    @property
    def REDIS_URL(self) -> str:
        """
        [What] 获取Redis连接URL
        [Why] Redis Queue需要连接字符串
        [How] 拼接Redis连接参数
        """
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @model_validator(mode="after")
    def _validate_test_token_safety(self) -> "Settings":
        """S-08: 生产环境禁止开启测试 Token 后门 + 禁止默认 SECRET_KEY"""
        if not self.DEBUG and self.ENABLE_TEST_TOKEN:
            raise RuntimeError("ENABLE_TEST_TOKEN 仅允许在 DEBUG 模式下使用")
        if not self.DEBUG and self.SECRET_KEY == "your-secret-key-change-in-production":
            raise RuntimeError("SECRET_KEY 必须通过环境变量设置，禁止使用默认值")
        return self


@lru_cache
def get_settings() -> Settings:
    """
    [What] 获取配置单例
    [Why] 避免重复读取环境变量
    [How] 使用lru_cache装饰器缓存配置实例
    """
    return Settings()
