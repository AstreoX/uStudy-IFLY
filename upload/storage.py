"""存储后端抽象层"""

import os
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import aiofiles

from config import get_settings


class StorageBackend(ABC):
    """存储后端抽象基类"""

    @abstractmethod
    async def save(self, file_data: bytes, filename: str, subdir: str = "") -> str:
        """保存文件，返回访问路径"""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """删除文件"""
        pass

    @abstractmethod
    def get_url(self, path: str) -> str:
        """获取文件访问 URL"""
        pass


class LocalStorage(StorageBackend):
    """本地文件存储"""

    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, file_data: bytes, filename: str, subdir: str = "") -> str:
        """保存文件到本地"""
        save_dir = self.base_dir / subdir if subdir else self.base_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        file_path = save_dir / filename
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(file_data)

        relative_path = f"/{self.base_dir.name}/{subdir}/{filename}" if subdir else f"/{self.base_dir.name}/{filename}"
        return relative_path

    async def delete(self, path: str) -> bool:
        """删除本地文件（带路径遍历防护）"""
        # Resolve the path and verify it's within base_dir
        file_path = (self.base_dir / Path(path.lstrip("/"))).resolve()
        base_resolved = self.base_dir.resolve()

        # Prevent path traversal attacks
        if not str(file_path).startswith(str(base_resolved)):
            raise ValueError(f"Path traversal detected: {path}")

        if file_path.exists():
            os.remove(file_path)
            return True
        return False

    def get_url(self, path: str) -> str:
        """获取文件 URL（相对路径）"""
        return path


@lru_cache(maxsize=1)
def get_storage() -> StorageBackend:
    """获取存储后端实例（单例模式）"""
    settings = get_settings()
    return LocalStorage(base_dir=settings.upload_dir)
