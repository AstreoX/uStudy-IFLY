"""Opt-in 1,500-page memory/regression acceptance test.

Run explicitly with ``RUN_PDF_STRESS=1 pytest -m slow
tests/rag/test_pdf_agentic_stress.py``. It is excluded from routine CI because
it creates 2,625 WebP assets.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from rag.pdf_agentic import expected_asset_count, render_pdf_visual_index


def _working_set_bytes() -> int:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(ProcessMemoryCounters),
            wintypes.DWORD,
        ]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        handle = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            raise OSError("GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize)

    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # Linux reports KiB; macOS reports bytes.
    return int(usage * 1024 if usage < 10_000_000 else usage)


@pytest.mark.slow
@pytest.mark.skipif(
    os.getenv("RUN_PDF_STRESS") != "1",
    reason="set RUN_PDF_STRESS=1 for the 1,500-page acceptance test",
)
def test_streaming_renderer_stays_below_512_mib_for_1500_pages(tmp_path: Path):
    fitz = pytest.importorskip("fitz")
    source = tmp_path / "1500-pages.pdf"
    pdf = fitz.open()
    for page_number in range(1, 1501):
        page = pdf.new_page(width=144, height=216)
        page.insert_text((12, 24), f"Page {page_number}", fontsize=8)
    pdf.save(source)
    pdf.close()

    peak = _working_set_bytes()

    def record_memory(_done: int, _total: int) -> None:
        nonlocal peak
        peak = max(peak, _working_set_bytes())

    manifest = render_pdf_visual_index(
        source,
        tmp_path / "rendered",
        max_pages=1500,
        render_dpi=160,
        render_max_pixels=8_000_000,
        webp_quality=85,
        max_image_bytes=4 * 1024 * 1024,
        lod_max_side=2048,
        max_derived_bytes=2 * 1024 * 1024 * 1024,
        min_free_disk_bytes=0,
        on_progress=record_memory,
    )

    assert manifest.page_count == 1500
    assert manifest.asset_count == expected_asset_count(1500) == 2625
    assert peak < 512 * 1024 * 1024
