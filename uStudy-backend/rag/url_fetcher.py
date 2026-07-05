"""URL content fetcher for link-type documents.

Supports:
- Webpage text extraction (via trafilatura)
- YouTube transcript extraction (via youtube-transcript-api)
- Bilibili / other platform subtitle extraction (via yt-dlp)
- Whisper API fallback for videos without subtitles
"""

from __future__ import annotations

import asyncio
import html as html_module
import logging
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
import trafilatura

from chat.tools.web_tools import _is_safe_url
from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_MAX_HTML_BYTES = 5 * 1024 * 1024  # 5MB
_SUBTITLE_EXTENSIONS = {".vtt", ".srt", ".ass", ".ssa", ".ttml"}

_VIDEO_HOST_PATTERNS = [
    re.compile(r"(?:[a-z]+\.)?youtube\.com"),
    re.compile(r"youtu\.be"),
    re.compile(r"(?:[a-z]+\.)?bilibili\.com"),
    re.compile(r"b23\.tv"),
    re.compile(r"(?:[a-z]+\.)?vimeo\.com"),
]

_YOUTUBE_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
)


@dataclass
class URLContentResult:
    """URL content extraction result."""

    content: str
    title: str
    content_type: str  # "webpage" | "video_transcript"
    source_url: str
    metadata: dict = field(default_factory=dict)


class URLFetchError(Exception):
    """Raised when URL content cannot be fetched."""


class URLContentFetcher:
    """Fetch and extract content from URLs for RAG processing."""

    async def fetch(self, url: str) -> URLContentResult:
        """Main entry point: dispatch to the appropriate handler based on URL type."""
        # _is_safe_url calls blocking socket.gethostbyname — run in thread
        is_safe, error = await asyncio.to_thread(_is_safe_url, url)
        if not is_safe:
            raise URLFetchError(f"URL 安全检查失败: {error}")

        if self._is_video_url(url):
            return await self._fetch_video_transcript(url)
        return await self._fetch_webpage(url)

    def _is_video_url(self, url: str) -> bool:
        """Check if URL belongs to a known video platform."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return any(pattern.fullmatch(hostname) for pattern in _VIDEO_HOST_PATTERNS)

    # ── Webpage extraction ──────────────────────────────────────────

    async def _fetch_webpage(self, url: str) -> URLContentResult:
        """Fetch and extract main content from a webpage using trafilatura."""
        timeout = settings.url_fetch_timeout_seconds
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                max_redirects=5,
                headers={"User-Agent": "Mozilla/5.0 (compatible; uStudyBot/1.0)"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Validate final URL after redirects (SSRF: redirect to internal IP)
                final_url = str(response.url)
                if final_url != url:
                    is_safe, error = await asyncio.to_thread(_is_safe_url, final_url)
                    if not is_safe:
                        raise URLFetchError(f"重定向目标安全检查失败: {error}")

                # Stream response to enforce size limit without OOM
                html = await self._read_response_with_limit(response)

        except URLFetchError:
            raise
        except httpx.HTTPStatusError as exc:
            raise URLFetchError(f"HTTP {exc.response.status_code}: 无法访问 {url}") from exc
        except httpx.RequestError as exc:
            raise URLFetchError(f"网络请求失败: {exc}") from exc

        extracted = await asyncio.to_thread(
            trafilatura.extract,
            html,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )

        if not extracted or not extracted.strip():
            raise URLFetchError("无法从页面提取有效文本内容")

        xml_output = await asyncio.to_thread(
            trafilatura.extract,
            html,
            output_format="xml",
            include_comments=False,
        )
        page_title = ""
        if xml_output:
            try:
                root = ET.fromstring(xml_output)
                page_title = root.attrib.get("title", "")
            except ET.ParseError:
                pass

        if not page_title:
            page_title = _extract_title_from_html(html)

        return URLContentResult(
            content=extracted,
            title=page_title or url,
            content_type="webpage",
            source_url=url,
            metadata={"content_length": len(extracted)},
        )

    async def _read_response_with_limit(self, response: httpx.Response) -> str:
        """Read response text, enforcing _MAX_HTML_BYTES to prevent OOM.

        Note: httpx AsyncClient.get() already downloads the full body for non-streaming
        requests, so this is a post-download guard. For true streaming protection,
        use client.stream() — but trafilatura needs the full HTML anyway.
        """
        content = response.content
        if len(content) > _MAX_HTML_BYTES:
            raise URLFetchError(
                f"页面过大 ({len(content) / 1024 / 1024:.1f}MB)，"
                f"超过 {_MAX_HTML_BYTES // 1024 // 1024}MB 限制"
            )
        return response.text

    # ── Video transcript extraction ─────────────────────────────────

    async def _fetch_video_transcript(self, url: str) -> URLContentResult:
        """Extract transcript from a video URL."""
        video_id = self._extract_youtube_video_id(url)
        if video_id:
            try:
                return await self._fetch_youtube_transcript(url, video_id)
            except URLFetchError:
                raise
            except asyncio.TimeoutError:
                logger.warning("YouTube transcript API 超时, 尝试 yt-dlp: %s", url)
            except Exception as exc:
                logger.warning(
                    "YouTube transcript API 失败, 尝试 yt-dlp: %s", exc, exc_info=True
                )

        # Fallback: yt-dlp for subtitles
        try:
            return await self._fetch_subtitles_via_ytdlp(url)
        except URLFetchError:
            raise
        except asyncio.TimeoutError:
            logger.warning("yt-dlp 字幕提取超时: %s", url)
        except Exception as exc:
            logger.warning("yt-dlp 字幕提取失败: %s", exc, exc_info=True)

        # Final fallback: download audio + Whisper
        if settings.openai_api_key:
            return await self._fetch_via_whisper(url)

        raise URLFetchError(
            "无法获取视频字幕。视频没有可用字幕，且未配置 Whisper API (OPENAI_API_KEY) 进行语音转录。"
        )

    def _extract_youtube_video_id(self, url: str) -> Optional[str]:
        match = _YOUTUBE_VIDEO_ID_RE.search(url)
        return match.group(1) if match else None

    async def _fetch_youtube_transcript(
        self, url: str, video_id: str
    ) -> URLContentResult:
        """Fetch YouTube transcript using youtube-transcript-api."""
        from youtube_transcript_api import YouTubeTranscriptApi

        timeout = settings.video_transcript_timeout_seconds

        def _get_transcript():
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list_transcripts(video_id)
            # Prefer manual transcripts, then auto-generated; prefer zh/en
            preferred_langs = ["zh-Hans", "zh", "en", "zh-Hant", "ja", "ko"]
            try:
                transcript = transcript_list.find_manually_created_transcript(
                    preferred_langs
                )
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(
                        preferred_langs
                    )
                except Exception:
                    # Fall back to whatever is available
                    transcript = next(iter(transcript_list))
            fetched = transcript.fetch()
            lines = [entry.text for entry in fetched]
            lang = transcript.language_code
            return "\n".join(lines), lang

        text, language = await asyncio.wait_for(
            asyncio.to_thread(_get_transcript),
            timeout=timeout,
        )

        if not text.strip():
            raise URLFetchError("YouTube 字幕内容为空")

        return URLContentResult(
            content=text,
            title=f"YouTube Video {video_id}",
            content_type="video_transcript",
            source_url=url,
            metadata={
                "video_id": video_id,
                "platform": "youtube",
                "language": language,
            },
        )

    async def _fetch_subtitles_via_ytdlp(self, url: str) -> URLContentResult:
        """Extract subtitles using yt-dlp (Bilibili, Vimeo, etc.)."""
        import yt_dlp

        timeout = settings.video_transcript_timeout_seconds

        def _extract():
            with tempfile.TemporaryDirectory() as tmpdir:
                opts = {
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": ["zh", "zh-Hans", "en", "ja", "ko", "all"],
                    "subtitlesformat": "vtt/srt/best",
                    "skip_download": True,
                    "outtmpl": str(Path(tmpdir) / "%(id)s.%(ext)s"),
                    "quiet": True,
                    "no_warnings": True,
                    "socket_timeout": 30,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        raise URLFetchError("yt-dlp 无法解析视频信息")

                    title = info.get("title", url)

                    # Check if subtitles are available
                    subs = info.get("subtitles") or {}
                    auto_subs = info.get("automatic_captions") or {}
                    all_subs = {**auto_subs, **subs}  # manual overrides auto

                    if not all_subs:
                        raise URLFetchError("视频没有可用字幕")

                    # Pick best language
                    preferred = ["zh-Hans", "zh", "en", "zh-Hant", "ja", "ko"]
                    chosen_lang = None
                    for lang in preferred:
                        if lang in all_subs:
                            chosen_lang = lang
                            break
                    if not chosen_lang:
                        chosen_lang = next(iter(all_subs))

                    # Download the subtitle file
                    dl_opts = {
                        **opts,
                        "subtitleslangs": [chosen_lang],
                        "skip_download": True,
                    }
                    with yt_dlp.YoutubeDL(dl_opts) as ydl2:
                        ydl2.download([url])

                    # Find subtitle files only (skip .info.json etc.)
                    sub_files = [
                        f for f in Path(tmpdir).glob("*.*")
                        if f.suffix.lower() in _SUBTITLE_EXTENSIONS
                    ]
                    text_parts = []
                    for sf in sub_files:
                        raw = sf.read_text(encoding="utf-8", errors="replace")
                        text_parts.append(_clean_subtitle_text(raw))

                    text = "\n".join(text_parts)
                    return text, title, chosen_lang

        text, title, language = await asyncio.wait_for(
            asyncio.to_thread(_extract),
            timeout=timeout,
        )

        if not text.strip():
            raise URLFetchError("提取的字幕内容为空")

        return URLContentResult(
            content=text,
            title=title,
            content_type="video_transcript",
            source_url=url,
            metadata={"platform": "yt-dlp", "language": language},
        )

    async def _fetch_via_whisper(self, url: str) -> URLContentResult:
        """Download audio via yt-dlp and transcribe with OpenAI Whisper API."""
        import yt_dlp
        from openai import AsyncOpenAI

        timeout = settings.whisper_timeout_seconds
        max_audio = settings.whisper_max_audio_bytes

        # Use TemporaryDirectory as context manager inside thread to ensure cleanup
        def _download_audio():
            tmpdir = tempfile.mkdtemp()
            try:
                out_path = str(Path(tmpdir) / "audio.%(ext)s")
                opts = {
                    "format": "bestaudio[filesize<25M]/bestaudio",
                    "outtmpl": out_path,
                    "quiet": True,
                    "no_warnings": True,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "64",
                        }
                    ],
                    "socket_timeout": 30,
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get("title", url) if info else url

                # Find downloaded audio file
                audio_files = list(Path(tmpdir).glob("audio.*"))
                if not audio_files:
                    raise URLFetchError("音频下载失败")
                audio_path = audio_files[0]

                if audio_path.stat().st_size > max_audio:
                    raise URLFetchError(
                        f"音频文件过大 ({audio_path.stat().st_size / 1024 / 1024:.1f}MB)，"
                        f"超过 Whisper API {max_audio // 1024 // 1024}MB 限制"
                    )

                # Read audio bytes into memory so tmpdir can be cleaned up
                audio_bytes = audio_path.read_bytes()
                audio_name = audio_path.name
                return audio_bytes, audio_name, title
            finally:
                shutil.rmtree(tmpdir, ignore_errors=True)

        audio_bytes, audio_name, title = await asyncio.wait_for(
            asyncio.to_thread(_download_audio),
            timeout=timeout,
        )

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        transcription = await asyncio.wait_for(
            client.audio.transcriptions.create(
                model="whisper-1",
                file=(audio_name, audio_bytes),
                response_format="text",
            ),
            timeout=timeout,
        )

        text = transcription if isinstance(transcription, str) else str(transcription)
        if not text.strip():
            raise URLFetchError("Whisper 转录结果为空")

        return URLContentResult(
            content=text,
            title=title,
            content_type="video_transcript",
            source_url=url,
            metadata={"platform": "whisper", "method": "audio_transcription"},
        )


def _extract_title_from_html(raw_html: str) -> str:
    """Extract <title> from HTML as fallback."""
    match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, re.IGNORECASE | re.DOTALL)
    if match:
        return html_module.unescape(match.group(1)).strip()
    return ""


def _clean_subtitle_text(raw: str) -> str:
    """Remove VTT/SRT formatting, timestamps, and duplicate lines."""
    lines = raw.splitlines()
    cleaned = []
    seen: set[str] = set()
    for raw_line in lines:
        stripped = raw_line.strip()
        # Skip VTT header, empty, numeric index, timestamp lines
        if not stripped or stripped == "WEBVTT":
            continue
        if re.match(r"^\d+$", stripped):
            continue
        if re.match(r"^[\d:.,\-> ]+$", stripped):
            continue
        # Remove inline VTT tags like <c> </c> <00:01:23.456>
        text = re.sub(r"<[^>]+>", "", stripped).strip()
        if text and text not in seen:
            seen.add(text)
            cleaned.append(text)
    return "\n".join(cleaned)
