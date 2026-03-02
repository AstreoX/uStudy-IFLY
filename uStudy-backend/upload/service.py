"""上传服务层"""

import io
from uuid import UUID, uuid4

from PIL import Image
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from db.models import User
from upload.storage import StorageBackend, get_storage

settings = get_settings()

# 图片格式 MIME 类型映射
MIME_TO_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

# Magic bytes 用于验证文件类型
MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",
}


def detect_mime_type(file_data: bytes) -> str | None:
    """通过 magic bytes 检测文件类型"""
    for magic, mime in MAGIC_BYTES.items():
        if file_data.startswith(magic):
            return mime
    # WebP 需要特殊处理
    if file_data[:4] == b"RIFF" and file_data[8:12] == b"WEBP":
        return "image/webp"
    return None


def validate_image(file_data: bytes, content_type: str | None) -> tuple[bool, str]:
    """验证图片文件"""
    # 检查文件大小
    if len(file_data) > settings.avatar_max_size_bytes:
        max_mb = settings.avatar_max_size_bytes / (1024 * 1024)
        return False, f"文件大小超过限制 ({max_mb:.0f}MB)"

    # 通过 magic bytes 检测实际类型
    detected_type = detect_mime_type(file_data)
    if detected_type is None:
        return False, "无法识别的文件格式"

    # 检查是否为允许的类型
    if detected_type not in settings.avatar_allowed_types:
        allowed = ", ".join(settings.avatar_allowed_types)
        return False, f"不支持的文件格式，仅支持: {allowed}"

    return True, detected_type


def process_avatar_image(file_data: bytes, output_size: int = 256) -> bytes:
    """处理头像图片：调整大小、压缩、去除元数据"""
    img = Image.open(io.BytesIO(file_data))

    # 转换为 RGB 模式（处理 RGBA 等格式）
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # 裁剪为正方形（从中心）
    width, height = img.size
    min_dim = min(width, height)
    left = (width - min_dim) // 2
    top = (height - min_dim) // 2
    img = img.crop((left, top, left + min_dim, top + min_dim))

    # 调整大小
    img = img.resize((output_size, output_size), Image.Resampling.LANCZOS)

    # 导出为 WebP（更小的文件大小，更好的质量）
    output = io.BytesIO()
    img.save(output, format="WEBP", quality=85, method=6)
    return output.getvalue()


async def upload_avatar(
    user_id: UUID,
    file_data: bytes,
    content_type: str | None,
    db: AsyncSession,
    storage: StorageBackend | None = None,
) -> str:
    """上传用户头像"""
    if storage is None:
        storage = get_storage()

    # 验证图片
    is_valid, result = validate_image(file_data, content_type)
    if not is_valid:
        raise ValueError(result)

    # 处理图片
    processed_data = process_avatar_image(file_data, settings.avatar_output_size)

    # 生成文件名
    filename = f"{user_id}_{uuid4().hex[:8]}.webp"

    # 保存文件
    avatar_url = await storage.save(processed_data, filename, subdir="avatars")

    # 更新数据库
    await db.execute(
        update(User).where(User.id == user_id).values(avatar_url=avatar_url)
    )
    await db.commit()

    return avatar_url
