# backend/main.py
"""
[What] FastAPI应用入口
[Why] 所有路由和中间件在此注册
[How] 创建FastAPI实例，注册路由和中间件
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.database import engine, Base

settings = get_settings()

# [What] 创建FastAPI应用实例
# [Why] 这是整个后端服务的核心
# [How] 使用FastAPI()构造函数
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# [What] 配置CORS中间件
# [Why] 微信小程序需要跨域访问后端API
# [How] 允许所有来源（开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# [What] 注册路由
# [Why] 路由定义API端点
# [How] 使用include_router导入各模块路由
from backend.routers import user as user_router
app.include_router(user_router.router)


@app.on_event("startup")
async def startup_event():
    """
    [What] 应用启动事件
    [Why] 启动时创建数据库表
    [How] 调用Base.metadata.create_all
    """
    # 注意：生产环境应使用Alembic迁移
    # Base.metadata.create_all(bind=engine)
    pass


@app.get("/")
async def root():
    """
    [What] 健康检查端点
    [Why] 用于监控服务是否正常运行
    [How] 返回简单的JSON响应
    """
    return {"message": "MegaWords API is running", "version": settings.APP_VERSION}


@app.get("/health")
async def health_check():
    """
    [What] 健康检查端点
    [Why] 用于负载均衡器和监控系统
    [How] 返回服务状态
    """
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=settings.BACKEND_PORT, reload=True)
