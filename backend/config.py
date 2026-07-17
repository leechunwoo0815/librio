# backend/config.py
"""
[What] 项目配置文件
[Why] 集中管理所有配置项，便于维护
[How] 使用pydantic-settings从环境变量读取配置
"""

from functools import lru_cache

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

    # 运营主体
    COMPANY_NAME: str = ""      # 微信小程序认证主体公司全称（用于隐私政策/资质展示）

    # Mock 网关开关（仅本地开发使用，生产环境必须关闭）
    MOCK_PAYMENT: bool = False  # 支付 Mock 网关（默认关闭，生产安全）
    MOCK_SMS: bool = False      # 短信 Mock 网关（生产必须关闭——真实 SDK 未接入时本地开发手动设为 True）

    # 生产短信服务商配置
    SMS_PROVIDER: str = "mock"          # mock / tencent / aliyun
    SMS_APP_ID: str = ""                # SDK AppID
    SMS_APP_KEY: str = ""               # SDK AppKey / AccessKeySecret
    SMS_SIGN_NAME: str = "DmkWords"    # 短信签名（需平台审核通过）
    SMS_TEMPLATE_CODE: str = ""         # 验证码模板 ID

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
        [How] 拼接MySQL连接参数
        """
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


@lru_cache
def get_settings() -> Settings:
    """
    [What] 获取配置单例
    [Why] 避免重复读取环境变量
    [How] 使用lru_cache装饰器缓存配置实例
    """
    s = Settings()
    if not s.DEBUG and s.SECRET_KEY == "your-secret-key-change-in-production":
        raise RuntimeError("SECRET_KEY 必须通过环境变量设置，禁止使用默认值")
    return s
