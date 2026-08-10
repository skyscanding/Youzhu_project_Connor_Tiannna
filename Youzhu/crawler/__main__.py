"""python -m crawler 入口。"""
import sys

from crawler.cli import main


def _force_utf8_stdio() -> None:
    """确保在非 UTF-8 控制台（Windows cp1252/cp936 等）下也能输出中文，避免 UnicodeEncodeError。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (ValueError, OSError):
            pass


if __name__ == "__main__":
    _force_utf8_stdio()
    report = main()
    summary = report.get("summary") or {} if report else {}
    if report is None:
        sys.exit(2)
    if summary.get("sources_total") and not summary.get("sources_ok"):
        sys.exit(1)
