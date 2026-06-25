"""初始化 web 静态资源占位 HTML — dev-time 一次性脚本.

历史: MAQ-17 (web/main.py FastAPI 9 端点) 落地时, 占位 HTML 是模块导入时
write_text 副作用 (NS4, MAQ-19). MAQ-22 review 复验: 模块级写文件让
pytest collection / TestClient / 生产环境启动都静默创建文件, 违反
"运行时不应有意外写文件" 的工程纪律. v1.1.1 起挪到这个 dev-time 脚本.

用法:
    uv run python scripts/init_static.py            # 写占位 HTML
    uv run python scripts/init_static.py --check    # 检查文件存在, 缺则 exit 1
    uv run python scripts/init_static.py --force    # 强制覆盖
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PLACEHOLDER_HTML = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<title>rag-demo</title></head><body>"
    "<h1>rag-demo</h1>"
    "<p>API available at <code>/api/health</code> etc.</p>"
    "<p>Static index placeholder — see MAQ-18 for full cold-start UI.</p>"
    "</body></html>"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--static-dir",
        type=Path,
        default=Path(__file__).parent.parent / "src" / "rag_demo" / "web" / "static",
        help="static 目录 (默认: src/rag_demo/web/static/)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="只检查 index.html 是否存在, 缺则 exit 1 (不写文件)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="强制覆盖已存在的 index.html",
    )
    args = parser.parse_args(argv)

    static_dir: Path = args.static_dir
    index_path = static_dir / "index.html"

    if args.check:
        if not index_path.exists():
            print(f"missing: {index_path}", file=sys.stderr)
            return 1
        print(f"ok: {index_path}")
        return 0

    static_dir.mkdir(parents=True, exist_ok=True)
    if index_path.exists() and not args.force:
        print(f"exists (skip): {index_path}")
        return 0
    index_path.write_text(_PLACEHOLDER_HTML, encoding="utf-8")
    print(f"wrote: {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
