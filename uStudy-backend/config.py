from functools import lru_cache

from pydantic import ConfigDict
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # 数据库
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/ustudy"
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 15
    db_pool_recycle_seconds: int = 1800

    # Redis (用于流式缓存)
    redis_url: str = "redis://localhost:6379/0"
    streaming_cache_ttl_seconds: int = 300  # 流式缓存 TTL: 5 分钟

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
    max_concurrent_devices: int = 3

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
    smtp_use_ssl: bool = False  # True for implicit SSL (port 465), e.g. Aliyun DM

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
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/markdown",
        "text/html",
        "text/csv",
        "application/epub+zip",
    ]
    document_allowed_extensions: list = [
        ".pdf", ".doc", ".docx", ".txt",
        ".xlsx", ".xls", ".pptx", ".ppt",
        ".md", ".html", ".htm", ".csv", ".epub",
    ]

    # OpenRouter / LLM 配置
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_bridge_url: str = ""  # JP bridge for region-restricted models (Gemini etc.)
    openrouter_model: str = "bytedance-seed/seed-1.6"
    gemini_model: str = "z-ai/glm-4.7-flash"
    llm_timeout_seconds: int = 300  # 5分钟
    llm_max_retries: int = 3
    llm_proxy_url: str = ""  # 可选：显式设置代理 URL，为空则使用系统环境变量

    # Web 搜索配置
    web_search_timeout_seconds: int = 30
    web_fetch_max_length: int = 3000

    # URL 内容获取配置
    url_fetch_timeout_seconds: int = 30
    video_transcript_timeout_seconds: int = 60
    whisper_timeout_seconds: int = 300
    whisper_max_audio_bytes: int = 25 * 1024 * 1024  # 25MB (OpenAI Whisper API limit)
    openai_api_key: str = ""  # for Whisper API

    # Crawl4AI (Docker service for JS rendering)
    crawl4ai_api_url: str = ""  # Docker 内部: http://crawl4ai:11235
    crawl4ai_api_token: str = ""  # Optional API token for Crawl4AI
    crawl4ai_timeout_seconds: int = 60
    crawl4ai_enabled: bool = False  # 部署后开启

    # Jina Reader (external API backup)
    jina_api_key: str = ""
    jina_reader_timeout_seconds: int = 30
    jina_reader_enabled: bool = True  # 默认开启（无需部署）

    # SearXNG (self-hosted meta-search engine)
    searxng_base_url: str = ""  # http://8.211.149.4:8888
    searxng_timeout_seconds: int = 15
    searxng_enabled: bool = False  # 部署后开启

    # Deep Crawl (multi-page BFS crawling)
    deep_crawl_max_pages: int = 20
    deep_crawl_max_depth: int = 3
    deep_crawl_timeout_seconds: int = 300
    deep_crawl_enabled: bool = False  # 部署后开启

    # 多渠道搜索配置
    semantic_scholar_timeout: int = 15
    wikipedia_timeout: int = 10
    bilibili_search_timeout: int = 15

    # RAG 配置
    # Embedding 模型配置
    embedding_model: str = "qwen/qwen3-embedding-8b"
    embedding_dimension: int = 2000  # HNSW 索引最大支持 2000 维
    embedding_batch_size: int = 20  # 每批处理的文本数量
    embedding_max_concurrent: int = 3  # embedding 并发批次数

    # 切片配置
    chunk_size_tokens: int = 600  # 目标切片大小（tokens）
    chunk_overlap_tokens: int = 100  # 切片重叠（tokens）
    chunk_min_size_tokens: int = 50  # 最小切片大小

    # 检索配置
    retrieval_top_k: int = 10  # 向量搜索返回数量

    # 混合搜索配置
    hybrid_search_enabled: bool = True       # 默认开启混合搜索
    hybrid_vector_weight: float = 0.7        # RRF 中向量权重
    hybrid_text_weight: float = 0.3          # RRF 中全文权重
    hybrid_rrf_k: int = 60                   # RRF 常数
    hybrid_fetch_k: int = 20                 # 每路搜索的候选数量

    # 自动 RAG 预注入配置
    rag_auto_inject_enabled: bool = True     # 默认开启
    rag_auto_inject_top_k: int = 3           # 预注入结果数（小值，节省 token）
    rag_auto_inject_threshold: float = 0.5   # 最低相似度（高于工具搜索的 0.3）

    # 嵌入缓存配置
    embedding_cache_enabled: bool = True
    embedding_cache_ttl_seconds: int = 3600

    # VLM 视觉处理配置
    vlm_processing_enabled: bool = True
    vlm_model: str = "qwen/qwen3-vl-8b-instruct"
    vlm_ocr_enabled: bool = True
    vlm_image_description_enabled: bool = True
    vlm_max_images_per_document: int = 30
    vlm_min_image_size_bytes: int = 5000       # 跳过 <5KB 小图
    vlm_max_image_size_bytes: int = 5242880    # 跳过 >5MB 大图
    vlm_max_concurrent: int = 3

    # 附件文本提取配置
    attachment_text_max_tokens: int = 10000  # 每个文件最大 token 数
    attachment_text_timeout_seconds: int = 30  # 提取超时（秒）
    attachment_cache_extracted_text: bool = True  # 是否缓存到数据库

    # 向量记忆系统配置
    memory_search_top_k_long_term: int = 5  # 长期记忆语义检索数量
    memory_search_top_k_space: int = 5  # 空间记忆语义检索数量
    memory_search_score_threshold: float = 0.3  # 最低相似度阈值
    memory_auto_extract_enabled: bool = True  # 是否启用自动记忆提取
    memory_extraction_model: str = "moonshotai/kimi-k2.5"  # 记忆提取用的 LLM 模型（空则使用默认模型）

    # 知识图谱生成配置
    knowledge_graph_model: str = "z-ai/glm-4.7-flash"  # 空则使用默认模型

    # 整卷综合评估配置
    quiz_evaluation_model: str = "z-ai/glm-4.7-flash"  # 空则使用默认模型

    # 掌握分评估配置
    mastery_evaluation_enabled: bool = True
    mastery_evaluation_model: str = "z-ai/glm-4.7-flash"  # 空则使用默认模型

    # 学习路径自动扩展
    learning_path_auto_expand_enabled: bool = True
    learning_path_expand_model: str = "moonshotai/kimi-k2.5"  # 空则使用默认模型
    learning_path_mastery_threshold: int = 80  # 掌握度阈值
    learning_path_ratio_threshold: float = 0.6  # 高掌握节点占比阈值

    # 学习建议配置
    suggestion_model: str = "moonshotai/kimi-k2.5"  # 学习建议生成用的 LLM 模型（空则使用默认模型）

    # 对话连续性配置
    conversation_continuity_enabled: bool = True  # 是否启用上一次对话上下文加载
    conversation_continuity_max_rounds: int = 2  # 加载上一次对话的最后几轮（1-5）
    conversation_continuity_max_content_length: int = 1000  # 单条消息最大截断长度

    # Artifact 生成配置
    artifact_model: str = "z-ai/glm-5"

    # 代码沙箱配置
    code_sandbox_timeout: int = 30
    code_sandbox_memory_mb: int = 256
    code_sandbox_max_code_length: int = 10000
    code_sandbox_max_output_length: int = 5000

    # 对话标题自动生成配置
    title_generation_enabled: bool = True
    title_generation_model: str = "qwen/qwen3-8b"
    title_generation_timeout: int = 10  # 秒

    # 支付宝配置
    alipay_app_id: str = ""
    alipay_app_private_key_path: str = "./certs/alipay_app_private_key.pem"
    alipay_public_key_path: str = "./certs/alipay_public_key.pem"
    alipay_sign_type: str = "RSA2"
    alipay_debug: bool = False  # True = sandbox gateway
    alipay_notify_url: str = ""  # e.g. https://api.ustudy.top/api/payment/alipay/notify
    alipay_return_url: str = ""  # e.g. https://ustudy.top/pages/activation/activation

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_flag(cls, value):
        """Allow DEBUG to come from release-style environment strings."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development"}:
                return True
            if normalized in {
                "0",
                "false",
                "no",
                "off",
                "release",
                "prod",
                "production",
            }:
                return False
        return value


@lru_cache
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()
