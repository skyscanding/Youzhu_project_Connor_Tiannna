"""python -m sourcelib：由种子数据重新生成信源库 JSON 文件。"""
import argparse
import sys
from pathlib import Path

from sourcelib.seed import CHANNELS, DOCUMENTS
from sourcelib.store import Library, save_library

DEFAULT_OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "sourcelib"


def main(out_dir: Path = DEFAULT_OUT_DIR) -> Path:
    library = Library(channels=tuple(CHANNELS), documents=tuple(DOCUMENTS))
    path = out_dir / "library.json"
    save_library(path, library)
    print(f"信源库已生成：{path}（渠道 {len(CHANNELS)}，文档 {len(DOCUMENTS)}）")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="python -m sourcelib", description="由种子数据生成信源库 JSON")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="输出目录（默认 data/sourcelib）")
    args = parser.parse_args()
    main(Path(args.out_dir))

