"""
修复执行器

输入：修复计划（由 planner.py 产出）+ 目标文件路径
输出：修复后的文件 + 执行日志

使用 edit_file 工具执行精确的 old_str/new_str 替换。
每次编辑前自动备份原文件。
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


# 执行日志记录
execution_log: list[dict[str, Any]] = []


def backup_file(file_path: str) -> str:
    """备份原文件，返回备份路径。"""
    src = Path(file_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = src.with_suffix(f".bak_{timestamp}")
    shutil.copy2(src, backup)
    return str(backup)


def execute_auto_fixes(
    file_path: str, plan: dict, text: str, lines: list[str]
) -> tuple[str, list[dict]]:
    """执行自动修复（Bug 类）。

    返回 (修改后的文本, 执行结果列表)。
    调用方负责将修改后的文本写回文件。
    """
    global execution_log
    execution_log = []

    fixes = plan.get("auto_fixes", [])
    if not fixes:
        return text, []

    modified_text = text
    results = []

    for fix in fixes:
        detector = fix["detector"]
        fix_type = fix.get("fix_type", "")
        line_num = fix["line"]

        try:
            if fix_type == "rename":
                modified_text, result = _fix_rename(modified_text, fix, line_num)
            elif fix_type == "downgrade_heading":
                modified_text, result = _fix_downgrade_heading(modified_text, fix, line_num)
            elif fix_type == "update_version":
                modified_text, result = _fix_update_version(modified_text, fix)
            elif fix_type == "add_field":
                modified_text, result = _fix_add_field(modified_text, fix)
            else:
                result = {"success": False, "message": f"未知修复类型: {fix_type}"}

            results.append(result)
            execution_log.append({
                "detector": detector,
                "fix_type": fix_type,
                "line": line_num,
                "success": result["success"],
                "message": result["message"],
            })

        except Exception as e:
            result = {"success": False, "message": str(e)}
            results.append(result)
            execution_log.append({
                "detector": detector,
                "fix_type": fix_type,
                "line": line_num,
                "success": False,
                "message": str(e),
            })

    return modified_text, results


def _fix_rename(text: str, fix: dict, line_num: int) -> tuple[str, dict]:
    """重命名版本编号。"""
    suggestion = fix.get("suggestion", "")
    # Extract old and new from suggestion: "将 v6.52.2 改为 v6.53.2"
    import re
    m = re.search(r"将\s*(v[\d.]+)\s*改为\s*(v[\d.]+)", suggestion)
    if not m:
        return text, {"success": False, "message": "无法解析重命名建议"}

    old_name = m.group(1)
    new_name = m.group(2)

    if old_name in text:
        text = text.replace(old_name, new_name)
        return text, {"success": True, "message": f"已将 {old_name} 改为 {new_name}"}
    else:
        return text, {"success": False, "message": f"未找到 {old_name}"}


def _fix_downgrade_heading(text: str, fix: dict, line_num: int) -> tuple[str, dict]:
    """降级标题：## → ###。"""
    suggestion = fix.get("suggestion", "")
    import re
    m = re.search(r"「## (.*?)」降级为「### (.*?)」", suggestion)
    if not m:
        return text, {"success": False, "message": "无法解析降级建议"}

    old_heading = f"## {m.group(1)}"
    new_heading = f"### {m.group(1)}"

    if old_heading in text:
        text = text.replace(old_heading, new_heading)
        return text, {"success": True, "message": f"已将标题降级: {old_heading} → {new_heading}"}
    else:
        return text, {"success": False, "message": f"未找到标题: {old_heading}"}


def _fix_update_version(text: str, fix: dict) -> tuple[str, dict]:
    """更新 YAML version 字段。"""
    suggestion = fix.get("suggestion", "")
    import re
    m = re.search(r"将 YAML version 更新为 '([\d.]+)'", suggestion)
    if not m:
        return text, {"success": False, "message": "无法解析版本更新建议"}

    new_version = m.group(1)
    old_pattern = re.compile(r'(\nversion:\s*")[\d.]+(")')
    if old_pattern.search(text):
        text = old_pattern.sub(rf'\g<1>{new_version}\g<2>', text)
        return text, {"success": True, "message": f"YAML version 已更新为 {new_version}"}
    else:
        return text, {"success": False, "message": "未找到 YAML version 字段"}


def _fix_add_field(text: str, fix: dict) -> tuple[str, dict]:
    """补全 YAML 缺失字段。"""
    suggestion = fix.get("suggestion", "")
    # In practice this needs more context to insert correctly
    return text, {"success": False, "message": f"YAML 补全需手动执行: {suggestion}"}


def get_execution_summary() -> dict:
    """获取执行摘要。"""
    total = len(execution_log)
    success = sum(1 for r in execution_log if r["success"])
    failed = total - success
    return {
        "total_operations": total,
        "successful": success,
        "failed": failed,
        "details": execution_log,
    }


def save_execution_log(output_dir: str) -> str:
    """将执行日志保存到文件。"""
    log_path = Path(output_dir) / f"execution_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    log_path.write_text(
        json.dumps(get_execution_summary(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(log_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python executor.py <plan.json> <SKILL.md路径> [--dry-run]")
        sys.exit(1)

    plan_path = sys.argv[1]
    file_path = sys.argv[2]
    dry_run = "--dry-run" in sys.argv

    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)

    text = Path(file_path).read_text(encoding="utf-8")
    lines = text.split("\n")

    if not dry_run:
        backup_file(file_path)

    modified_text, results = execute_auto_fixes(file_path, plan, text, lines)

    if not dry_run and modified_text != text:
        Path(file_path).write_text(modified_text, encoding="utf-8")

    summary = get_execution_summary()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
