"""URL content fetcher for link-type documents.

Supports:
- Webpage text extraction (via ContentRouter: trafilatura → Crawl4AI → Jina)
- YouTube transcript extraction (via youtube-transcript-api)
- Bilibili subtitle extraction (via Bilibili API → yt-dlp fallback)
- Other platform subtitle extraction (via yt-dlp)
- Whisper API fallback for videos without subtitles
- Webpage content fallback when all transcript methods fail
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from crawler.ssrf import is_safe_url as _is_safe_url
from config import get_settings
from crawler.router import ContentRouter

logger = logging.getLogger(__name__)
settings = get_settings()

_SUBTITLE_EXTENSIONS = {".vtt", ".srt", ".ass", ".ssa", ".ttml"}

_VIDEO_HOST_PATTERNS = [
    re.compile(r"(?:[a-z]+\.)?youtube\.com"),
    re.compile(r"youtu\.be"),
    re.compile(r"(?:[a-z]+\.)?bilibili\.com"),
    re.compile(r"b23\.tv"),
    re.compile(r"(?:[a-z]+\.)?vimeo\.com"),
]

_SHORT_URL_HOSTS = {"b23.tv"}

_YOUTUBE_VIDEO_ID_RE = re.compile(
    r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})"
)

_BILIBILI_BVID_RE = re.compile(r"bilibili\.com/video/(BV[a-zA-Z0-9]+)")
_BILIBILI_AVID_RE = re.compile(r"bilibili\.com/video/av(\d+)")


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

    def __init__(self) -> None:
        self._content_router = ContentRouter()

    async def fetch(self, url: str) -> URLContentResult:
        """Main entry point: dispatch to the appropriate handler based on URL type."""
        # Step 0: resolve short URLs (b23.tv → bilibili.com)
        resolved_url = await self._resolve_short_url(url)

        # Step 1: SSRF check on the resolved URL
        is_safe, error = await asyncio.to_thread(_is_safe_url, resolved_url)
        if not is_safe:
            raise URLFetchError(f"URL 安全检查失败: {error}")

        # Step 2: dispatch
        if self._is_video_url(resolved_url):
            return await self._fetch_video_transcript(resolved_url)
        return await self._fetch_webpage(resolved_url)

    # ── Short URL resolution ─────────────────────────────────────

    async def _resolve_short_url(self, url: str) -> str:
        """Resolve short URLs (e.g. b23.tv) to their final destination.

        Returns the resolved URL, or the original if resolution fails.
        """
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname not in _SHORT_URL_HOSTS:
            return url

        # _SHORT_URL_HOSTS is a small allowlist of known public short-URL
        # services (currently only b23.tv).  The HEAD request targets that
        # public host; the *resolved* URL is SSRF-checked afterward in fetch().
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                max_redirects=5,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            ) as client:
                resp = await client.head(url)
                resolved = str(resp.url)
                if resolved != url:
                    logger.info("短链接已解析: %s → %s", url, resolved)
                return resolved
        except (httpx.TooManyRedirects, httpx.RequestError, httpx.HTTPStatusError) as exc:
            logger.warning("短链接解析失败，使用原始 URL: %s — %s", url, exc)
            return url

    # ── URL type detection ───────────────────────────────────────

    def _is_video_url(self, url: str) -> bool:
        """Check if URL belongs to a known video platform."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return any(pattern.fullmatch(hostname) for pattern in _VIDEO_HOST_PATTERNS)

    def _is_bilibili_url(self, url: str) -> bool:
        """Check if URL is a Bilibili video page."""
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        return hostname == "bilibili.com" or hostname.endswith(".bilibili.com")

    # ── Webpage extraction ──────────────────────────────────────────

    async def _fetch_webpage(self, url: str) -> URLContentResult:
        """Fetch and extract main content from a webpage using ContentRouter.

        ContentRouter fallback chain: trafilatura → Crawl4AI → Jina Reader.
        """
        result = await self._content_router.extract(url)
        if not result:
            raise URLFetchError("无法从页面提取有效文本内容（所有提取方式均失败）")

        return URLContentResult(
            content=result.content,
            title=result.title,
            content_type=result.content_type,
            source_url=url,
            metadata={
                "content_length": len(result.content),
                "extraction_method": result.extraction_method,
            },
        )

    # ── Video transcript extraction ─────────────────────────────────

    async def _fetch_video_transcript(self, url: str) -> URLContentResult:
        """Extract transcript from a video URL.

        Fallback chain:
        1. YouTube Transcript API (YouTube only)
        2. Bilibili Subtitle API (Bilibili only)
        3. yt-dlp subtitles (all platforms)
        4. Whisper API (if OPENAI_API_KEY configured)
        5. Webpage content fallback
        """
        # Tier 1: YouTube Transcript API
        video_id = self._extract_youtube_video_id(url)
        if video_id:
            try:
                return await self._fetch_youtube_transcript(url, video_id)
            except URLFetchError:
                raise
            except asyncio.TimeoutError:
                logger.warning("YouTube transcript API 超时, 尝试下一层: %s", url)
            except Exception as exc:
                logger.warning(
                    "YouTube transcript API 失败, 尝试下一层: %s", exc, exc_info=True
                )

        # Tier 2: Bilibili Subtitle API (direct API, more reliable than yt-dlp)
        if self._is_bilibili_url(url):
            try:
                return await self._fetch_bilibili_subtitle(url)
            except URLFetchError:
                pass  # fall through to yt-dlp
            except asyncio.TimeoutError:
                logger.warning("Bilibili 字幕 API 超时, 尝试 yt-dlp: %s", url)
            except Exception as exc:
                logger.warning(
                    "Bilibili 字幕 API 失败, 尝试 yt-dlp: %s", exc, exc_info=True
                )

        # Tier 3: yt-dlp for subtitles
        try:
            return await self._fetch_subtitles_via_ytdlp(url)
        except URLFetchError:
            pass  # fall through to Whisper / webpage
        except asyncio.TimeoutError:
            logger.warning("yt-dlp 字幕提取超时: %s", url)
        except Exception as exc:
            logger.warning("yt-dlp 字幕提取失败: %s", exc, exc_info=True)

        # Tier 4: download audio + Whisper
        if settings.openai_api_key:
            try:
                return await self._fetch_via_whisper(url)
            except URLFetchError:
                pass  # fall through to webpage
            except asyncio.TimeoutError:
                logger.warning("Whisper 语音转录超时: %s", url)
            except Exception as exc:
                logger.warning("Whisper 语音转录失败: %s", exc, exc_info=True)

        # Tier 5: webpage content fallback (title, description, etc.)
        logger.info("所有视频字幕提取方式均失败，尝试提取网页内容: %s", url)
        try:
            result = await self._fetch_webpage(url)
            return URLContentResult(
                content=result.content,
                title=result.title,
                content_type=result.content_type,
                source_url=result.source_url,
                metadata={
                    **result.metadata,
                    "video_fallback": True,
                    "note": "视频字幕不可用，已提取页面文本内容",
                },
            )
        except URLFetchError:
            raise URLFetchError(
                "无法获取视频内容。视频字幕提取失败，网页内容提取也失败了。"
                "可能原因：视频没有字幕、网页需要登录、或网络问题。"
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

    # ── Bilibili subtitle extraction ────────────────────────────────

    async def _fetch_bilibili_subtitle(self, url: str) -> URLContentResult:
        """Fetch Bilibili subtitles via player API.

        Uses Bilibili's web API to get subtitle data directly, which is
        more reliable than yt-dlp for Bilibili auto-generated subtitles.
        """
        # Extract BV/AV ID
        bv_match = _BILIBILI_BVID_RE.search(url)
        av_match = _BILIBILI_AVID_RE.search(url)
        if not bv_match and not av_match:
            raise URLFetchError("无法从 URL 提取 Bilibili 视频 ID")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com",
        }
        cookies = {"buvid3": str(uuid.uuid4()) + "infoc"}

        async with httpx.AsyncClient(
            timeout=15, headers=headers, cookies=cookies
        ) as client:
            # Step 1: get video info (cid, title) via /x/web-interface/view
            params: dict[str, str | int] = {}
            if bv_match:
                params["bvid"] = bv_match.group(1)
            elif av_match:
                params["aid"] = int(av_match.group(1))
            else:
                raise URLFetchError("无法从 URL 提取 Bilibili 视频 ID")

            view_resp = await client.get(
                "https://api.bilibili.com/x/web-interface/view", params=params
            )
            view_resp.raise_for_status()
            view_data = view_resp.json()

            if view_data.get("code") != 0:
                raise URLFetchError(
                    f"Bilibili 视频信息获取失败: {view_data.get('message')}"
                )

            video_info = view_data["data"]
            title = video_info.get("title", url)
            cid = video_info["cid"]
            aid = video_info["aid"]

            # Step 2: get subtitle list via /x/player/wbi/v2
            player_resp = await client.get(
                "https://api.bilibili.com/x/player/wbi/v2",
                params={"aid": aid, "cid": cid},
            )
            player_resp.raise_for_status()
            player_data = player_resp.json()

            subtitle_info = player_data.get("data", {}).get("subtitle", {})
            subtitle_list = subtitle_info.get("subtitles", [])

            if not subtitle_list:
                raise URLFetchError("Bilibili 视频没有可用字幕")

            # Step 3: pick best language
            preferred_order = ["zh-CN", "zh-Hans", "zh", "ai-zh", "en", "ai-en"]
            chosen = None
            for pref in preferred_order:
                for sub in subtitle_list:
                    if sub.get("lan", "") == pref:
                        chosen = sub
                        break
                if chosen:
                    break
            if not chosen:
                chosen = subtitle_list[0]

            # Step 4: download subtitle JSON (with SSRF + domain validation)
            sub_url = chosen.get("subtitle_url") or ""
            if not sub_url:
                raise URLFetchError("Bilibili 字幕 URL 为空")
            if sub_url.startswith("//"):
                sub_url = "https:" + sub_url

            parsed_sub = urlparse(sub_url)
            sub_host = (parsed_sub.hostname or "").lower()
            if not (sub_host.endswith(".bilibili.com") or sub_host.endswith(".bilivideo.com")):
                raise URLFetchError(f"Bilibili 字幕 URL 指向非 Bilibili 域名: {sub_host}")

            is_safe, err = _is_safe_url(sub_url)
            if not is_safe:
                raise URLFetchError(f"Bilibili 字幕 URL 安全检查失败: {err}")

            sub_resp = await client.get(sub_url)
            sub_resp.raise_for_status()
            sub_data = sub_resp.json()

            # Step 5: extract text from subtitle body
            lines = [item["content"] for item in sub_data.get("body", [])]
            text = "\n".join(lines)

        if not text.strip():
            raise URLFetchError("Bilibili 字幕内容为空")

        logger.info(
            "Bilibili 字幕提取成功: %s, 语言: %s, %d 行",
            title,
            chosen.get("lan", "unknown"),
            len(lines),
        )

        return URLContentResult(
            content=text,
            title=title,
            content_type="video_transcript",
            source_url=url,
            metadata={
                "platform": "bilibili",
                "language": chosen.get("lan", "unknown"),
                "aid": aid,
                "cid": cid,
            },
        )

    # ── yt-dlp subtitle extraction ──────────────────────────────────

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

    # ── Whisper audio transcription ─────────────────────────────────

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
