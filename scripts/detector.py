"""
SKILL.md 问题检测器引擎

输入：结构树 JSON（由 parser.py 产出）
输出：问题清单（按严重度分级：bug / structure / optimize）

包含 10 个检测器：
  D1 - 版本编号连续性
  D2 - 模块聚合度
  D3 - 标题层级冲突
  D4 - Description 精简度
  D5 - 重复内容
  D6 - 章节编号一致性
  D7 - Version 一致性
  D8 - 代码块语言标记
  D9 - 引用有效性
  D10 - YAML 完整性
"""

import re
import json
from typing import Any


SEVERITY_BUG = "bug"
SEVERITY_STRUCTURE = "structure"
SEVERITY_OPTIMIZE = "optimize"


def detect_all(tree: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """运行全部 10 个检测器，返回合并后的问题清单。"""
    issues = []
    issues.extend(detect_d1_version_continuity(tree))
    issues.extend(detect_d2_module_cohesion(tree))
    issues.extend(detect_d3_heading_conflict(tree))
    issues.extend(detect_d4_description_bloat(tree))
    issues.extend(detect_d5_duplicate_content(tree, text))
    issues.extend(detect_d6_chapter_consistency(tree))
    issues.extend(detect_d7_version_consistency(tree))
    issues.extend(detect_d8_code_language(tree))
    issues.extend(detect_d9_reference_validity(tree))
    issues.extend(detect_d10_yaml_completeness(tree))
    return issues


# ── D1: 版本编号连续性 ──────────────────────────────────────────

def detect_d1_version_continuity(tree: dict) -> list[dict]:
    """检测版本编号跳跃、错位、残留。

    规则：属于同一上下文（同一章节前后文）的版本号应连续。
    如果出现 v6.52.2 在 v6.53 章节中，标记为错位。
    """
    issues = []
    refs = tree.get("version_refs", [])
    headings = tree.get("headings", [])

    # Build heading context map
    heading_lines = {h["line"]: h["text"] for h in headings}

    for ref in refs:
        line = ref["line"]
        version_str = ref["version"]
        # Find the nearest heading above this line
        context_heading = None
        for h in reversed(headings):
            if h["line"] < line:
                context_heading = h["text"]
                break

        if context_heading:
            # Check if version's major.minor matches the heading context
            ver_base = f"v{ref['major']}.{ref['minor']}"
            ver_patch = f".{ref['patch']}" if ref["patch"] is not None else ""
            full_ver = f"{ver_base}{ver_patch}"

            # Detect if a sub-version appears in wrong section
            heading_ver_match = re.search(r"v(\d+)\.(\d+)", context_heading)
            if heading_ver_match:
                heading_major = int(heading_ver_match.group(1))
                heading_minor = int(heading_ver_match.group(2))

                if ref["major"] == heading_major and ref["minor"] != heading_minor and ref["patch"] is not None:
                    # Sub-version in different section → potential numbering bug
                    issues.append({
                        "detector": "D1",
                        "severity": SEVERITY_BUG,
                        "line": line,
                        "message": f"版本子编号疑似错位：{full_ver} 出现在 {context_heading} 节中，"
                                   f"归属应为 v{heading_major}.{heading_minor}.x",
                        "fix_type": "rename",
                        "suggestion": f"将 {full_ver} 改为 v{heading_major}.{heading_minor}.{ref['patch']}",
                    })

    return issues


# ── D2: 模块聚合度 ──────────────────────────────────────────────

# Topic keywords for grouping sections
TOPIC_GROUPS = {
    "抖音": ["抖音", "短视频", "中长视频", "跳出率", "2s"],
    "GitHub": ["GitHub", "开源项目", "Trending", "仓库"],
    "封面设计": ["封面", "缩略图", "thumbnail", "3:4", "9:16", "4:3"],
    "审核": ["审核", "内容审核", "审查", "违禁"],
    "ECC": ["ECC", "缓存", "积分", "内容创作"],
    "动画": ["动画", "CSS", "转场", "视觉", "UI-UX"],
}


def detect_d2_module_cohesion(tree: dict) -> list[dict]:
    """检测同主题章节是否被无关内容隔开过远。

    如果同主题章节间隔 >500 行，且中间有不同主题的内容，标记为分裂。
    """
    issues = []
    headings = tree.get("headings", [])
    h2_headings = [h for h in headings if h["level"] == 2]

    # Assign topic group to each heading
    for h in h2_headings:
        h["topic_group"] = _classify_topic(h["text"])

    # Find same-topic headings that are far apart
    for topic_name, keywords in TOPIC_GROUPS.items():
        same_topic = [h for h in h2_headings if h.get("topic_group") == topic_name]
        if len(same_topic) >= 2:
            for i in range(len(same_topic) - 1):
                gap = same_topic[i + 1]["line"] - same_topic[i]["line"]
                if gap > 500:
                    # Check if there's unrelated content between them
                    in_between = [h for h in h2_headings
                                  if same_topic[i]["line"] < h["line"] < same_topic[i + 1]["line"]
                                  and h.get("topic_group") != topic_name]
                    if in_between:
                        issues.append({
                            "detector": "D2",
                            "severity": SEVERITY_STRUCTURE,
                            "line": same_topic[i]["line"],
                            "message": f"同主题「{topic_name}」章节被 {gap} 行无关内容隔开："
                                       f"「{same_topic[i]['text']}」→「{same_topic[i+1]['text']}」",
                            "fix_type": "move_section",
                            "suggestion": f"将「{same_topic[i+1]['text']}」移动到「{same_topic[i]['text']}」之后",
                        })

    return issues


def _classify_topic(text: str) -> str | None:
    """根据标题文本归入主题组。"""
    for group_name, keywords in TOPIC_GROUPS.items():
        for kw in keywords:
            if kw in text:
                return group_name
    return None


# ── D3: 标题层级冲突 ────────────────────────────────────────────

def detect_d3_heading_conflict(tree: dict) -> list[dict]:
    """检测子模块内部的 ## 中文编号标题与顶级九大章编号冲突。

    例：v6.6 内部出现 ## 一、项目概览，与顶级 ## 一、核心概述 冲突。
    """
    issues = []
    headings = tree.get("headings", [])
    top_chapters = [h for h in headings if h.get("is_chapter")]

    chapter_nums = set()
    for ch in top_chapters:
        m = re.match(r"^([一二三四五六七八九十])、", ch["text"])
        if m:
            chapter_nums.add(m.group(1))

    # Find non-chapter ## headings with same numbering
    for h in headings:
        if h["level"] == 2 and not h.get("is_chapter"):
            m = re.match(r"^([一二三四五六七八九十])、", h["text"])
            if m and m.group(1) in chapter_nums:
                parent = _find_parent_section(headings, h["line"])
                issues.append({
                    "detector": "D3",
                    "severity": SEVERITY_BUG,
                    "line": h["line"],
                    "message": f"标题「## {h['text']}」与顶级章节编号冲突，"
                               f"位于 {parent} 区域内",
                    "fix_type": "downgrade_heading",
                    "suggestion": f"将「## {h['text']}」降级为「### {h['text']}」",
                })

    return issues


def _find_parent_section(headings: list[dict], line: int) -> str:
    """找到某行所属的父章节标题。"""
    parent = "未知区域"
    for h in sorted(headings, key=lambda x: -x["line"]):
        if h["line"] < line:
            parent = h["text"]
            break
    return parent


# ── D4: Description 精简度 ──────────────────────────────────────

def detect_d4_description_bloat(tree: dict) -> list[dict]:
    """检测 YAML description 是否冗长（>300 字符或包含版本号堆砌）。"""
    issues = []
    desc = tree.get("yaml", {}).get("description", "")
    if not desc:
        return issues

    if len(desc) > 300:
        version_matches = re.findall(r"v\d+\.\d+", desc)
        issues.append({
            "detector": "D4",
            "severity": SEVERITY_OPTIMIZE,
            "line": tree.get("yaml_start", -1) + 1,
            "message": f"description 过长（{len(desc)} 字符），"
                       f"包含 {len(version_matches)} 个版本号引用",
            "fix_type": "simplify_description",
            "suggestion": "建议精简为一句核心能力描述，移除版本号线性堆砌",
        })

    return issues


# ── D5: 重复内容 ────────────────────────────────────────────────

def detect_d5_duplicate_content(tree: dict, text: str) -> list[dict]:
    """检测相邻章节间的重复内容（simhash 近似）。"""
    issues = []
    lines = text.split("\n")
    chapters = tree.get("chapter_ranges", [])

    for i in range(len(chapters) - 1):
        ch1 = chapters[i]
        ch2 = chapters[i + 1]

        # Get content of both chapters
        content1 = "\n".join(lines[ch1["start_line"]:ch1["end_line"]])
        content2 = "\n".join(lines[ch2["start_line"]:ch2["end_line"]])

        # Simple overlap check: find common lines of >50 chars
        lines1 = {l.strip() for l in content1.split("\n") if len(l.strip()) > 50}
        lines2 = {l.strip() for l in content2.split("\n") if len(l.strip()) > 50}
        common = lines1 & lines2

        if len(common) >= 3:
            issues.append({
                "detector": "D5",
                "severity": SEVERITY_STRUCTURE,
                "line": ch2["start_line"],
                "message": f"「{ch1['title']}」与「{ch2['title']}」存在 {len(common)} 行重复内容",
                "fix_type": "deduplicate",
                "suggestion": "检查是否为有意重复，若非则删除重复段落",
            })

    return issues


# ── D6: 章节编号一致性 ──────────────────────────────────────────

CHAPTER_NUMBERS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def detect_d6_chapter_consistency(tree: dict) -> list[dict]:
    """检测中文编号（一~九）是否连续无跳跃。"""
    issues = []
    headings = tree.get("headings", [])
    top_chapters = [h for h in headings if h.get("is_chapter")]

    found_nums = []
    for ch in top_chapters:
        m = re.match(r"^([一二三四五六七八九十])、", ch["text"])
        if m:
            found_nums.append((m.group(1), ch["line"], ch["text"]))

    if not found_nums:
        return issues

    first_idx = CHAPTER_NUMBERS.index(found_nums[0][0])
    for i, (num_char, line, text) in enumerate(found_nums):
        expected_idx = first_idx + i
        if expected_idx >= len(CHAPTER_NUMBERS):
            break
        expected_char = CHAPTER_NUMBERS[expected_idx]
        if num_char != expected_char:
            issues.append({
                "detector": "D6",
                "severity": SEVERITY_STRUCTURE,
                "line": line,
                "message": f"章节编号跳跃：期望「{expected_char}、」但出现「{num_char}、」({text})",
                "fix_type": "renumber",
                "suggestion": f"将「{num_char}、」改为「{expected_char}、」",
            })

    return issues


# ── D7: Version 一致性 ──────────────────────────────────────────

def detect_d7_version_consistency(tree: dict) -> list[dict]:
    """检测 YAML version 字段与内容中最新版本号是否一致。"""
    issues = []
    yaml_version = tree.get("yaml", {}).get("version", "").strip('"')
    refs = tree.get("version_refs", [])

    if not refs or not yaml_version:
        return issues

    # Find the highest version in content
    max_ver = max(refs, key=lambda r: (r["major"], r["minor"], r.get("patch") or 0))
    max_ver_str = f"{max_ver['major']}.{max_ver['minor']}"

    if yaml_version != max_ver_str:
        issues.append({
            "detector": "D7",
            "severity": SEVERITY_BUG,
            "line": tree.get("yaml_start", 0),
            "message": f"YAML version='{yaml_version}' 与内容中最新版本 v{max_ver_str} 不一致",
            "fix_type": "update_version",
            "suggestion": f"将 YAML version 更新为 '{max_ver_str}'",
        })

    return issues


# ── D8: 代码块语言标记 ──────────────────────────────────────────

def detect_d8_code_language(tree: dict) -> list[dict]:
    """检测代码块是否缺少语言标记。"""
    issues = []
    for cb in tree.get("code_blocks", []):
        if cb["language"] is None:
            issues.append({
                "detector": "D8",
                "severity": SEVERITY_OPTIMIZE,
                "line": cb["start"],
                "message": f"第 {cb['start']} 行代码块缺少语言标记（{cb['line_count']} 行）",
                "fix_type": "add_language",
                "suggestion": "添加语言标记，如 ```python 或 ```bash",
            })

    return issues


# ── D9: 引用有效性 ──────────────────────────────────────────────

def detect_d9_reference_validity(tree: dict) -> list[dict]:
    """检测内部引用（如「见 v6.8 节」）的目标是否存在。"""
    issues = []
    refs = tree.get("internal_refs", [])
    headings = tree.get("headings", [])

    heading_texts = {h["text"] for h in headings}

    for ref in refs:
        target = ref["target_version"]
        # Check if any heading contains this version
        found = any(target in htext for htext in heading_texts)
        if not found:
            issues.append({
                "detector": "D9",
                "severity": SEVERITY_OPTIMIZE,
                "line": ref["line"],
                "message": f"内部引用「{ref['ref_text']}」指向的 v{target} 节不存在",
                "fix_type": "fix_reference",
                "suggestion": "移除或修正该引用",
            })

    return issues


# ── D10: YAML 完整性 ────────────────────────────────────────────

def detect_d10_yaml_completeness(tree: dict) -> list[dict]:
    """检查 YAML frontmatter 是否包含 name/description/version。"""
    issues = []
    yaml = tree.get("yaml", {})
    required = ["name", "description", "version"]

    for field in required:
        if field not in yaml or not yaml[field]:
            issues.append({
                "detector": "D10",
                "severity": SEVERITY_BUG,
                "line": tree.get("yaml_start", 0),
                "message": f"YAML frontmatter 缺少必填字段「{field}」",
                "fix_type": "add_field",
                "suggestion": f"添加 {field}: <值>",
            })

    return issues


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python detector.py <structure_tree.json>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        tree = json.load(f)

    # Also need raw text for D5
    text = ""
    if len(sys.argv) >= 3:
        text = open(sys.argv[2], encoding="utf-8").read()

    issues = detect_all(tree, text)
    print(json.dumps(issues, ensure_ascii=False, indent=2))
