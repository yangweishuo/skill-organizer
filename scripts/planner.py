"""
修复计划生成器

输入：问题清单（由 detector.py 产出）
输出：修复计划（auto / manual 分流，按严重度排序）
"""

import json
from typing import Any

SEVERITY_BUG = "bug"
SEVERITY_STRUCTURE = "structure"
SEVERITY_OPTIMIZE = "optimize"


def generate_plan(issues: list[dict[str, Any]]) -> dict[str, Any]:
    """生成修复计划，将问题按严重度分流。"""
    auto_fixes = []      # Bug 类，自动执行
    manual_fixes = []    # 结构类，需确认
    suggestions = []     # 优化类，仅报告

    for issue in issues:
        if issue["severity"] == SEVERITY_BUG:
            auto_fixes.append(issue)
        elif issue["severity"] == SEVERITY_STRUCTURE:
            manual_fixes.append(issue)
        else:
            suggestions.append(issue)

    # Sort each group by detector number
    for group in [auto_fixes, manual_fixes, suggestions]:
        group.sort(key=lambda x: x["detector"])

    plan = {
        "summary": {
            "total_issues": len(issues),
            "bug_count": len(auto_fixes),
            "structure_count": len(manual_fixes),
            "optimize_count": len(suggestions),
        },
        "auto_fixes": auto_fixes,
        "manual_fixes": manual_fixes,
        "suggestions": suggestions,
    }

    # Generate execution steps for auto fixes
    plan["execution_steps"] = _generate_steps(auto_fixes)

    return plan


def _generate_steps(issues: list[dict]) -> list[dict]:
    """为自动修复生成执行步骤。"""
    steps = []
    for issue in issues:
        step = {
            "detector": issue["detector"],
            "line": issue["line"],
            "action": issue.get("fix_type", "unknown"),
            "description": issue["message"],
        }
        steps.append(step)
    return steps


def format_report(plan: dict) -> str:
    """格式化修复计划为可读报告。"""
    s = plan["summary"]
    lines = [
        "=" * 60,
        "  SKILL.md 检测报告",
        "=" * 60,
        f"  问题总数: {s['total_issues']}",
        f"  🔴 Bug (自动修复): {s['bug_count']}",
        f"  🟡 结构 (需确认):  {s['structure_count']}",
        f"  🟢 优化 (建议):    {s['optimize_count']}",
        "=" * 60,
    ]

    if plan["auto_fixes"]:
        lines.append("\n── 🔴 自动修复项 ──")
        for fix in plan["auto_fixes"]:
            lines.append(f"  [{fix['detector']}] L{fix['line']}: {fix['message']}")
            lines.append(f"     → {fix.get('suggestion', 'N/A')}")

    if plan["manual_fixes"]:
        lines.append("\n── 🟡 需确认项 ──")
        for fix in plan["manual_fixes"]:
            lines.append(f"  [{fix['detector']}] L{fix['line']}: {fix['message']}")
            lines.append(f"     → {fix.get('suggestion', 'N/A')}")

    if plan["suggestions"]:
        lines.append("\n── 🟢 优化建议 ──")
        for sug in plan["suggestions"]:
            lines.append(f"  [{sug['detector']}] L{sug['line']}: {sug['message']}")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python planner.py <issues.json>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        issues = json.load(f)

    plan = generate_plan(issues)
    print(format_report(plan))
    print("\n--- JSON ---")
    print(json.dumps(plan, ensure_ascii=False, indent=2))
