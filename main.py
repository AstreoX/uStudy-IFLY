import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from activation.router import router as activation_router
from agents.router import router as agents_router
from attachments.router import router as attachments_router
from auth.router import router as auth_router
from chat.router import router as chat_router
from config import get_settings
from documents.router import router as documents_router
from feedback.router import router as feedback_router
from notifications.router import router as notifications_router
from quizzes.router import router as quizzes_router
from scheduler.core import get_scheduler_lifespan
from usage.router import router as usage_router
from rag.router import router as rag_router
from spaces.router import router as spaces_router
from upload.router import router as upload_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    from notifications.pg_notify import start_listener, stop_listener

    async with get_scheduler_lifespan():
        await start_listener()
        try:
            yield
        finally:
            await stop_listener()


app = FastAPI(
    title="uStudy API",
    description="uStudy 学习平台后端 API",
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    password_sensitive_paths = {
        "/api/auth/register",
        "/api/auth/register-with-code",
        "/api/auth/reset-password",
    }
    if request.url.path in password_sensitive_paths:
        for error in exc.errors():
            loc = error.get("loc", [])
            if any(field in ("password", "new_password") for field in loc):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": {
                            "code": "WEAK_PASSWORD",
                            "message": error.get("msg", "密码强度不足"),
                        }
                    },
                )
    return await request_validation_exception_handler(request, exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器：捕获所有未处理的异常
    确保返回正确的 JSON 格式和 CORS 头
    """
    import logging
    import traceback

    logging.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}")
    logging.error(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "INTERNAL_ERROR",
                "message": "服务器内部错误，请稍后重试"
            }
        }
    )


# CORS 配置
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:9000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8080",
    "http://127.0.0.1:9000",
]

PROD_ORIGINS = [
    "https://ustudy.app",
    "https://www.ustudy.app",
    "https://app.ustudy.app",
    # 服务器 IP（Alpha 测试用）
    "http://121.199.164.168",
    "http://121.199.164.168:8000",
    # 本地开发
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
    "http://localhost:8080",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS if settings.debug else PROD_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# 挂载静态文件目录（头像等上传文件）
uploads_dir = Path(settings.upload_dir)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# 注册路由
app.include_router(auth_router)
app.include_router(activation_router)
app.include_router(upload_router)
app.include_router(attachments_router)
app.include_router(agents_router)
app.include_router(spaces_router)
app.include_router(quizzes_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(rag_router)
app.include_router(feedback_router)
app.include_router(usage_router)
app.include_router(notifications_router)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok"}


@app.get("/")
async def root():
    """根路由"""
    return {"message": "Welcome to uStudy API"}
