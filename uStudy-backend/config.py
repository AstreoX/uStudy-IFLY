import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings, NoDecode

logger = logging.getLogger(__name__)

def _parse_string_list(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _is_http_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


class Settings(BaseSettings):
    """应用配置"""

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
    app_env: str = "experiment"
    debug: bool = False
    public_api_base_url: str = "https://ustudy.top"
    public_web_base_url: str = "https://ustudy.top"
    public_app_base_url: str = "https://ustudy.top"
    download_base_url: str = "https://ustudy.top"
    support_contact_email: str = "contact@ustudy.top"
    public_registration_enabled: bool = True
    auth_email_enabled: bool = True
    apple_login_enabled: bool = False
    space_creation_enabled: bool = False
    cors_allow_local_network: bool = False
    cors_dev_origins: Annotated[list[str], NoDecode] = [
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
    cors_prod_origins: Annotated[list[str], NoDecode] = [
        "https://ustudy.top",
        # Explicit local development origins; the deployed Web app is same-origin.
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ]

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
    smtp_host: str = "smtp.mailtrap.io"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@ustudy.top"
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

    # DashScope / LLM 配置
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_bridge_url: str = ""
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimaxi.com/v1"
    background_llm_model: str = "MiniMax-M2.7-highspeed"
    llm_default_model: str = "z-ai/glm-5.3-flash"
    gemini_model: str = "MiniMax-M2.7-highspeed"
    quiz_reasoning_model: str = "MiniMax-M2.7-highspeed"
    llm_timeout_seconds: int = 60  # 非流式请求默认超时
    llm_stream_connect_timeout_seconds: int = 10
    llm_stream_read_timeout_seconds: int = 600
    llm_stream_write_timeout_seconds: int = 30
    llm_stream_pool_timeout_seconds: int = 30
    llm_max_retries: int = 3
    llm_proxy_url: str = ""  # 可选：显式设置代理 URL，为空则使用系统环境变量
    llm_tool_result_max_chars: int = 20000
    llm_context_max_chars: int = 120000

    # 图片生成统一走 OpenAI Images API 兼容中转（GPT Image 2）
    image_generation_base_url: str = "https://openapi.center"
    image_generation_api_key: str = ""  # Optional dedicated key; falls back to OPENAI_API_KEY for openai_images
    image_generation_model: str = "gpt-image-2"
    image_generation_timeout_seconds: int = 90
    image_generation_size: str = "1024x1024"
    image_generation_quality: str = "low"
    image_generation_output_format: str = "png"

    # 上下文工具（auto 模式异步检索）
    context_tools_enabled: bool = True           # 启用上下文工具（auto 模式）
    context_fallback_injection: bool = True      # AI 未调用上下文工具时自动注入已完成的检索结果

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
    embedding_model: str = "text-embedding-v3"
    embedding_dimension: int = 1024  # DashScope text-embedding-v3 最大合法维度
    embedding_batch_size: int = 20  # 每批处理的文本数量
    embedding_max_concurrent: int = 3  # embedding 并发批次数

    # 切片配置
    chunk_size_tokens: int = 600  # 目标切片大小（tokens）
    chunk_overlap_tokens: int = 100  # 切片重叠（tokens）
    chunk_min_size_tokens: int = 50  # 最小切片大小

    # 检索配置
    retrieval_top_k: int = 10  # 向量搜索返回数量
    rag_backend: str = "hybrid"  # haystack | hybrid | vector
    rag_enable_rerank: bool = False
    rag_dense_top_k: int = 20
    rag_sparse_top_k: int = 20
    rag_rerank_top_k: int = 8
    rag_final_top_k: int = 5
    rag_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    rag_enable_query_expansion: bool = False
    rag_enable_semantic_splitter: bool = False

    # 混合搜索配置
    hybrid_search_enabled: bool = True       # 默认开启混合搜索
    hybrid_vector_weight: float = 0.7        # RRF 中向量权重
    hybrid_text_weight: float = 0.3          # RRF 中全文权重
    hybrid_rrf_k: int = 60                   # RRF 常数
    hybrid_fetch_k: int = 20                 # 每路搜索的候选数量

    # 自动 RAG 预注入配置
    rag_auto_inject_enabled: bool = True     # 默认开启
    rag_auto_inject_top_k: int = 3           # 预注入结果数（小值，节省 token）
    rag_auto_inject_threshold: float = 0.55  # 最低相似度（高于工具搜索的 0.3）

    # Haystack mirror/index settings
    haystack_mirror_enabled: bool = True
    haystack_use_pgvector_retrievers: bool = True
    haystack_schema_name: str = "public"
    haystack_table_name: str = "haystack_documents"
    haystack_hnsw_index_name: str = "haystack_documents_hnsw_idx"
    haystack_keyword_index_name: str = "haystack_documents_keyword_idx"
    haystack_keyword_language: str = "simple"
    haystack_vector_type: str = "vector"
    haystack_search_strategy: str = "hnsw"

    # 嵌入缓存配置
    embedding_cache_enabled: bool = True
    embedding_cache_ttl_seconds: int = 3600

    # VLM 视觉处理配置
    vlm_processing_enabled: bool = True
    vlm_model: str = "qwen3.6-plus"
    vlm_ocr_enabled: bool = True
    vlm_image_description_enabled: bool = True
    vlm_min_image_size_bytes: int = 5000       # 跳过 <5KB 小图
    vlm_max_image_size_bytes: int = 5242880    # 跳过 >5MB 大图
    vlm_max_concurrent: int = 3

    # PDF Agentic RAG visual indexing. Derived files live outside the public
    # upload tree and are addressed by private, relative storage keys.
    pdf_agentic_enabled: bool = True
    pdf_private_dir: str = "private-rag"
    pdf_max_pages: int = 1500
    pdf_render_dpi: int = 160
    pdf_render_max_pixels: int = 8_000_000
    pdf_webp_quality: int = 85
    pdf_max_image_bytes: int = 4 * 1024 * 1024
    pdf_lod_max_side: int = 2048
    pdf_max_derived_bytes: int = 2 * 1024 * 1024 * 1024
    pdf_min_free_disk_bytes: int = 5 * 1024 * 1024 * 1024
    pdf_toc_scan_max_pages: int = 96
    pdf_toc_max_pages: int = 64
    pdf_toc_agent_max_rounds: int = 16
    pdf_processing_lease_seconds: int = 300
    pdf_processing_max_attempts: int = 4
    pdf_processing_max_concurrent_jobs: int = 1
    pdf_staging_retention_seconds: int = 86400
    rag_media_max_images: int = 4
    rag_media_max_bytes: int = 8 * 1024 * 1024

    # 附件文本提取配置
    attachment_text_max_tokens: int = 10000  # 每个文件最大 token 数
    attachment_text_timeout_seconds: int = 30  # 提取超时（秒）
    attachment_cache_extracted_text: bool = True  # 是否缓存到数据库
    use_base64_for_images: bool = True

    # 向量记忆系统配置
    memory_search_top_k_long_term: int = 5  # 长期记忆语义检索数量
    memory_search_top_k_space: int = 5  # 空间记忆语义检索数量
    memory_search_score_threshold: float = 0.3  # 最低相似度阈值
    memory_auto_extract_enabled: bool = True  # 是否启用自动记忆提取
    memory_extraction_model: str = "MiniMax-M2.7-highspeed"  # 记忆提取用的 LLM 模型

    # 知识图谱生成配置
    knowledge_graph_model: str = "MiniMax-M2.7-highspeed"
    knowledge_graph_timeout_seconds: int = 90  # 图谱生成通常比普通补全更慢
    knowledge_graph_max_tokens: int = 1024  # 图谱输出结构固定，限制输出长度以降低超时概率

    # 文档知识图谱提取配置
    document_kg_max_concurrent_extractions: int = 5  # Phase 1 并发 LLM 调用数
    document_kg_max_chunks: int = 200  # 单次任务最大处理 chunk 数

    # 整卷综合评估配置
    quiz_evaluation_model: str = "MiniMax-M2.7-highspeed"

    # 掌握分评估配置
    mastery_evaluation_enabled: bool = True
    mastery_evaluation_model: str = "MiniMax-M2.7-highspeed"
    # 论文评估层：候选节点相关性二分类 + 掌握变化五分类。
    # 训练完成并配置 checkpoint 前保持关闭，运行时自动沿用原 LLM 分支。
    mastery_dual_task_enabled: bool = False
    mastery_dual_task_checkpoint_path: str = ""
    mastery_dual_task_max_candidates: int = 10
    mastery_dual_task_max_length: int = 512
    mastery_dual_task_batch_size: int = 16
    mastery_dual_task_device: str = "cpu"
    mastery_dual_task_relevance_threshold: float = 0.55
    # 融合权重均表示双任务 BERT 分支的权重；剩余权重属于原 LLM 分支。
    mastery_fusion_relevance_weight: float = 0.7
    mastery_fusion_change_weight: float = 0.5

    # 学习路径自动扩展
    learning_path_auto_expand_enabled: bool = True
    learning_path_expand_model: str = "MiniMax-M2.7-highspeed"
    learning_path_mastery_threshold: int = 80  # 掌握度阈值
    learning_path_ratio_threshold: float = 0.6  # 高掌握节点占比阈值

    # 学习建议配置
    suggestion_model: str = "MiniMax-M2.7-highspeed"  # 学习建议生成用的 LLM 模型

    # 对话连续性配置
    conversation_continuity_enabled: bool = True  # 是否启用上一次对话上下文加载
    conversation_continuity_max_rounds: int = 2  # 加载上一次对话的最后几轮（1-5）
    conversation_continuity_max_content_length: int = 1000  # 单条消息最大截断长度

    # Artifact 生成配置
    artifact_model: str = "z-ai/glm-5.3-flash"
    artifact_timeout_seconds: int = 300

    # Teacher Presentation Agent control plane. The complete agent runs in a
    # separately isolated server container; the FastAPI app only exposes a
    # project-scoped capability gateway and private artifact storage.
    presentation_agent_gateway_base_url: str = (
        "http://backend:8000/api/internal/presentation-agent/runs"
    )
    presentation_sandbox_manager_url: str = "http://presentation-sandbox-manager:8090"
    presentation_sandbox_manager_token: str = ""
    presentation_private_dir: str = "private-presentations"

    # 代码沙箱配置
    code_sandbox_timeout: int = 30
    code_sandbox_memory_mb: int = 256
    code_sandbox_max_code_length: int = 10000
    code_sandbox_max_output_length: int = 5000

    # Isolated assignment OJ. Disabled unless the manager/executor security
    # preflight has passed; the application never falls back to subprocess.
    oj_enabled: bool = False
    oj_manager_url: str = "http://oj-manager:8091"
    oj_manager_token: str = ""
    oj_manager_token_file: str = ""
    oj_sample_rate_per_minute: int = 10
    oj_source_max_bytes: int = 65536
    oj_sample_retention_hours: int = 24
    oj_request_timeout_seconds: float = 15.0
    oj_run_poll_seconds: float = 0.5
    oj_run_timeout_seconds: int = 90

    @property
    def oj_manager_token_resolved(self) -> str:
        if self.oj_manager_token:
            return self.oj_manager_token.strip()
        if self.oj_manager_token_file:
            try:
                return Path(self.oj_manager_token_file).read_text(encoding="utf-8").strip()
            except OSError:
                return ""
        return ""

    # 对话标题自动生成配置
    title_generation_enabled: bool = True
    title_generation_model: str = "MiniMax-M2.7-highspeed"
    title_generation_timeout: int = 10  # 秒


    @field_validator("cors_dev_origins", "cors_prod_origins", mode="before")
    @classmethod
    def parse_origin_list(cls, value):
        """Allow CORS origins to be configured as comma-separated env strings."""
        return _parse_string_list(value)

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
