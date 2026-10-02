"""Verify the streaming CLI against a large TMX file without keeping output."""
import argparse
import ctypes
import json
import os
import re
import sys
import tempfile
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"%(?:\d+\$)?[A-Za-z]")


def _windows_peak_memory():
    if os.name != "nt":
        return None

    from ctypes import wintypes

    class ProcessMemoryCountersEx(ctypes.Structure):
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
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_current_process = kernel32.GetCurrentProcess
    get_current_process.restype = wintypes.HANDLE
    process_handle = get_current_process()
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    get_memory_info = psapi.GetProcessMemoryInfo
    get_memory_info.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCountersEx),
        wintypes.DWORD,
    ]
    get_memory_info.restype = wintypes.BOOL
    if not get_memory_info(process_handle, ctypes.byref(counters), counters.cb):
        return None
    return counters.PeakWorkingSetSize, counters.PrivateUsage


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tmx_file", type=Path, help="TMX input file to stream")
    args = parser.parse_args()
    input_path = args.tmx_file
    if not input_path.is_absolute():
        input_path = project_root / input_path
    if not input_path.is_file():
        parser.error(f"TMX file not found: {input_path}")

    env = os.environ.copy()
    source_path = str(project_root / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        path for path in (source_path, env.get("PYTHONPATH", "")) if path
    )
    sys.path.insert(0, source_path)
    from typer.testing import CliRunner

    from tmx_processor.cli import app

    with tempfile.TemporaryDirectory(prefix="tmx-stream-check-") as temp_dir:
        output_path = Path(temp_dir) / "streamed.jsonl"
        result = CliRunner().invoke(
            app,
            [
                "convert",
                str(input_path),
                "-o",
                str(output_path),
                "--fmt",
                "jsonl",
                "--streaming",
                "--no-dedupe",
                "--preserve-placeholders",
            ],
        )
        if result.exit_code:
            print(result.output, file=sys.stderr)
            if result.exception:
                raise result.exception
            return result.exit_code

        records = 0
        placeholders = 0
        with output_path.open(encoding="utf-8") as output:
            for line in output:
                record = json.loads(line)
                records += 1
                placeholders += len(PLACEHOLDER_RE.findall(record["source"]))
                placeholders += len(PLACEHOLDER_RE.findall(record["target"]))

        summary = (
            f"STREAM_OK input_bytes={input_path.stat().st_size} "
            f"records={records} placeholders={placeholders} "
            f"output_bytes={output_path.stat().st_size}"
        )
        peak_memory = _windows_peak_memory()
        if peak_memory:
            peak_working_set, private_bytes = peak_memory
            summary += (
                f" peak_working_set_mib={peak_working_set / (1024 * 1024):.1f}"
                f" private_bytes_mib={private_bytes / (1024 * 1024):.1f}"
            )
        else:
            summary += " peak_memory=unavailable"
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
