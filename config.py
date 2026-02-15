from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # 数据库
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/ustudy"

    # 应用
    app_env: str = "development"
    debug: bool = True

    # 安全
    secret_key: str = "dev-secret-key"

    # JWT 配置
    jwt_secret_key: str = "jwt-dev-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Apple Sign-In
    apple_client_id: str = ""
    apple_team_id: str = ""

    # 邮件配置
    email_provider: str = "resend"  # "resend" | "smtp"
    resend_api_key: str = ""
    smtp_host: str = "smtp.mailtrap.io"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@ustudy.app"
    smtp_from_name: str = "uStudy"
    smtp_use_tls: bool = True

    # 验证码配置
    verification_code_expire_minutes: int = 10
    verification_code_length: int = 6
    verification_code_rate_limit_seconds: int = 60
    verification_code_max_attempts: int = 5

    # verification_token 配置
    verification_token_expire_minutes: int = 5

    # 文件上传配置
    upload_dir: str = "uploads"
    avatar_max_size_bytes: int = 2 * 1024 * 1024  # 2MB
    avatar_output_size: int = 256  # 头像输出尺寸（像素）
    avatar_allowed_types: list = ["image/jpeg", "image/png", "image/webp"]

    # 文档上传配置
    document_max_size_bytes: int = 10 * 1024 * 1024  # 10MB
    document_allowed_types: list = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]
    document_allowed_extensions: list = [".pdf", ".doc", ".docx", ".txt"]

    # OpenRouter / LLM 配置
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "google/gemini-3-flash-preview"
    gemini_model: str = "google/gemini-3-flash-preview"
    llm_timeout_seconds: int = 300  # 5分钟
    llm_max_retries: int = 3
    llm_proxy_url: str = ""  # 可选：显式设置代理 URL，为空则使用系统环境变量

    # Web 搜索配置
    web_search_timeout_seconds: int = 30
    web_fetch_max_length: int = 3000

    # RAG 配置
    # Embedding 模型配置
    embedding_model: str = "qwen/qwen3-embedding-8b"
    embedding_dimension: int = 2000  # HNSW 索引最大支持 2000 维
    embedding_batch_size: int = 20  # 每批处理的文本数量

    # 切片配置
    chunk_size_tokens: int = 600  # 目标切片大小（tokens）
    chunk_overlap_tokens: int = 100  # 切片重叠（tokens）
    chunk_min_size_tokens: int = 50  # 最小切片大小

    # 检索配置
    retrieval_top_k: int = 10  # 向量搜索返回数量
    rerank_top_k: int = 5  # 重排序后返回数量
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # 附件文本提取配置
    attachment_text_max_tokens: int = 10000  # 每个文件最大 token 数
    attachment_text_timeout_seconds: int = 30  # 提取超时（秒）
    attachment_cache_extracted_text: bool = True  # 是否缓存到数据库


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
