"""
SKILL.md 结构树解析器

输入：SKILL.md 文件路径
输出：结构树 JSON（标题层级、YAML元信息、代码块、版本引用、内部引用）
"""

import re
import json
from pathlib import Path
from typing import Any


def parse_skill_md(file_path: str) -> dict[str, Any]:
    """解析 SKILL.md，返回结构树。"""
    text = Path(file_path).read_text(encoding="utf-8")
    lines = text.split("\n")

    tree: dict[str, Any] = {
        "file_path": file_path,
        "file_size_kb": round(len(text.encode("utf-8")) / 1024, 1),
        "total_lines": len(lines),
        "yaml": {},
        "headings": [],
        "code_blocks": [],
        "version_refs": [],
        "internal_refs": [],
        "yaml_start": -1,
        "yaml_end": -1,
    }

    in_yaml = False
    in_code = False
    code_block_start = -1
    yaml_lines = []

    heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$")
    version_pattern = re.compile(r"v(\d+)\.(\d+)(?:\.(\d+))?")
    ref_pattern = re.compile(r"(?:见|参见|参考|详见)\s*v?(\d+\.\d+)\s*(?:节|章|模块)")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # YAML frontmatter detection
        if i == 0 and stripped == "---":
            in_yaml = True
            tree["yaml_start"] = i
            continue
        if in_yaml and stripped == "---":
            in_yaml = False
            tree["yaml_end"] = i
            # Parse collected YAML lines into key: value pairs
            for yl in yaml_lines:
                if ":" in yl:
                    key, _, val = yl.partition(":")
                    tree["yaml"][key.strip()] = val.strip()
            continue
        if in_yaml:
            yaml_lines.append(stripped)
            continue

        # Code block tracking
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_block_start = i
            else:
                in_code = False
                lang = stripped[3:].strip() if len(stripped) > 3 else ""
                tree["code_blocks"].append({
                    "start": code_block_start,
                    "end": i,
                    "language": lang or None,
                    "line_count": i - code_block_start - 1,
                })
            continue

        if in_code:
            continue

        # Heading detection
        m = heading_pattern.match(stripped)
        if m:
            heading = {
                "line": i,
                "level": len(m.group(1)),
                "text": m.group(2).strip(),
                "is_chapter": False,
            }
            # Detect top-level chapter headings (## 一、, ## 二、 etc.)
            if heading["level"] == 2 and re.match(r"^[一二三四五六七八九十]、", heading["text"]):
                heading["is_chapter"] = True
            tree["headings"].append(heading)

        # Version reference extraction
        for vm in version_pattern.finditer(stripped):
            ver_str = vm.group(0)
            major, minor = int(vm.group(1)), int(vm.group(2))
            patch = int(vm.group(3)) if vm.group(3) else None
            tree["version_refs"].append({
                "line": i,
                "version": ver_str,
                "major": major,
                "minor": minor,
                "patch": patch,
                "context": stripped[:100],
            })

        # Internal reference extraction
        for rm in ref_pattern.finditer(stripped):
            tree["internal_refs"].append({
                "line": i,
                "ref_text": rm.group(0),
                "target_version": rm.group(1),
                "context": stripped,
            })

    # Post-processing: detect adjacent heading groups (for module cohesion)
    tree["chapter_ranges"] = _detect_chapter_ranges(tree["headings"], lines)

    return tree


def _detect_chapter_ranges(headings: list[dict], lines: list[str]) -> list[dict]:
    """Detect the line ranges of each chapter."""
    chapters = []
    chapter_h2 = [h for h in headings if h["level"] == 2]

    for i, h in enumerate(chapter_h2):
        start = h["line"]
        end = chapter_h2[i + 1]["line"] - 1 if i + 1 < len(chapter_h2) else len(lines) - 1
        chapters.append({
            "title": h["text"],
            "start_line": start,
            "end_line": end,
            "line_count": end - start,
        })

    return chapters


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parser.py <SKILL.md路径>")
        sys.exit(1)

    tree = parse_skill_md(sys.argv[1])
    print(json.dumps(tree, ensure_ascii=False, indent=2))
