"""配置测试"""

import pytest

from config import Settings


class TestJWTConfig:
    """JWT 配置测试"""

    def test_jwt_secret_key_exists(self):
        """JWT 密钥配置存在"""
        settings = Settings()
        assert hasattr(settings, "jwt_secret_key")
        assert settings.jwt_secret_key is not None

    def test_jwt_algorithm_default(self):
        """JWT 算法默认值"""
        settings = Settings()
        assert settings.jwt_algorithm == "HS256"

    def test_access_token_expire_minutes_default(self):
        """Access Token 过期时间默认 15 分钟"""
        settings = Settings()
        assert settings.access_token_expire_minutes == 15

    def test_refresh_token_expire_days_default(self):
        """Refresh Token 过期时间默认 7 天"""
        settings = Settings()
        assert settings.refresh_token_expire_days == 7


class TestPublicConfig:
    """公共运行时配置测试"""

    def test_public_domain_defaults_use_experiment_single_origin(self):
        settings = Settings()
        assert settings.app_env == "experiment"
        assert settings.public_api_base_url == "https://ustudy.top"
        assert settings.public_web_base_url == "https://ustudy.top"
        assert settings.public_app_base_url == "https://ustudy.top"
        assert settings.download_base_url == "https://ustudy.top"
        assert settings.support_contact_email == "contact@ustudy.top"

    def test_cors_defaults_only_include_experiment_and_local_origins(self):
        settings = Settings()
        assert "https://ustudy.top" in settings.cors_prod_origins
        assert "https://api.ustudy.cc" not in settings.cors_prod_origins
        assert "http://localhost:5173" in settings.cors_prod_origins

    def test_experiment_features_are_safe_by_default(self):
        settings = Settings()
        assert settings.public_registration_enabled is True
        assert settings.auth_email_enabled is True
        assert settings.apple_login_enabled is False
        assert settings.space_creation_enabled is False
        assert settings.learning_path_auto_expand_enabled is True

    def test_cors_env_can_be_comma_separated(self):
        settings = Settings(cors_prod_origins="https://a.test, https://b.test")
        assert settings.cors_prod_origins == ["https://a.test", "https://b.test"]

    def test_image_generation_defaults(self):
        settings = Settings()
        assert settings.use_base64_for_images is True
        assert settings.image_generation_base_url == "https://openapi.center"
        assert settings.image_generation_api_key == ""
        assert settings.image_generation_model == "gpt-image-2"
        assert settings.image_generation_timeout_seconds == 90
        assert settings.image_generation_size == "1024x1024"
        assert settings.image_generation_quality == "low"
        assert settings.image_generation_output_format == "png"

    def test_background_llm_defaults_use_deepseek(self):
        settings = Settings(_env_file=None)

        assert settings.minimax_base_url == "https://api.minimaxi.com/v1"
        assert settings.background_llm_model == "deepseek/deepseek-v4.1-flash"
        assert settings.gemini_model == settings.background_llm_model
        assert settings.quiz_reasoning_model == settings.background_llm_model
        assert settings.memory_extraction_model == settings.background_llm_model
        assert settings.knowledge_graph_model == settings.background_llm_model
        assert settings.quiz_evaluation_model == settings.background_llm_model
        assert settings.mastery_evaluation_model == settings.background_llm_model
        assert settings.learning_path_expand_model == settings.background_llm_model
        assert settings.suggestion_model == settings.background_llm_model
        assert settings.title_generation_model == settings.background_llm_model
        assert settings.artifact_model == settings.background_llm_model
        assert settings.presentation_llm_model == settings.background_llm_model
        assert settings.vlm_model == settings.background_llm_model

    def test_teacher_presentation_agent_defaults(self):
        settings = Settings(_env_file=None)
        assert settings.presentation_agent_gateway_base_url.endswith(
            "/api/internal/presentation-agent/runs"
        )
        assert settings.presentation_sandbox_manager_url == (
            "http://presentation-sandbox-manager:8090"
        )
        assert settings.presentation_sandbox_manager_token == ""
        assert settings.presentation_private_dir == "private-presentations"
