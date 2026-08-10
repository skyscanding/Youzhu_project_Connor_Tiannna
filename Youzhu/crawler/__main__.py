"""python -m crawler 入口。"""
import sys

from crawler.cli import main

if __name__ == "__main__":
    report = main()
    summary = report.get("summary") or {} if report else {}
    if report is None:
        sys.exit(2)
    if summary.get("sources_total") and not summary.get("sources_ok"):
        sys.exit(1)
