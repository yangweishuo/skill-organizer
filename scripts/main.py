"""
skill-organizer 主入口

管道调度器：Parser → Detector → Planner → Executor → Learner

用法:
  python main.py <SKILL.md路径>           # 混合模式（默认）
  python main.py <SKILL.md路径> --dry-run  # 分析模式，仅输出报告
  python main.py <SKILL.md路径> --auto     # 全自动模式，跳过确认
  python main.py --stats                   # 查看学习数据
"""

import json
import sys
from pathlib import Path

# Add parent scripts dir to path
sys.path.insert(0, str(Path(__file__).parent))

from parser import parse_skill_md
from detector import detect_all
from planner import generate_plan, format_report
from executor import execute_auto_fixes, backup_file, save_execution_log
from learner import Learner


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # --stats mode
    if sys.argv[1] == "--stats":
        rules_dir = Path(__file__).parent.parent / "rules"
        learner = Learner(str(rules_dir))
        stats = learner.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return

    # Normal mode
    file_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    auto_mode = "--auto" in sys.argv

    if not Path(file_path).exists():
        print(f"错误: 文件不存在: {file_path}")
        sys.exit(1)

    print(f"正在分析: {file_path}")
    print(f"文件大小: {round(Path(file_path).stat().st_size / 1024, 1)} KB")
    print()

    # Stage 1: Parse
    tree = parse_skill_md(file_path)
    text = Path(file_path).read_text(encoding="utf-8")
    lines = text.split("\n")

    # Check if large file → adaptive strategy
    rules_dir = Path(__file__).parent.parent / "rules"
    learner = Learner(str(rules_dir))
    strategy = learner.get_strategy()

    if tree["file_size_kb"] > 300 and strategy.get("large_file_chunking", True):
        print(f"⚠ 大文件检测（{tree['file_size_kb']}KB），启用分段分析策略")
        print()

    # Stage 2: Detect
    issues = detect_all(tree, text)
    print(f"检测完成: 发现 {len(issues)} 个问题")
    print()

    # Stage 3: Plan
    plan = generate_plan(issues)
    print(format_report(plan))
    print()

    if dry_run:
        print("[分析模式] 未执行修复。")
        return

    # Stage 4: Execute auto fixes
    if plan["auto_fixes"]:
        if not auto_mode:
            print(f"即将自动修复 {len(plan['auto_fixes'])} 个 Bug 类问题...")

        backup_path = backup_file(file_path)
        print(f"已备份: {backup_path}")

        modified_text, results = execute_auto_fixes(file_path, plan, text, lines)

        if modified_text != text:
            Path(file_path).write_text(modified_text, encoding="utf-8")
            success_count = sum(1 for r in results if r.get("success"))
            print(f"自动修复完成: {success_count}/{len(results)} 成功")
        else:
            print("自动修复未产生变更")
    else:
        print("无自动修复项")

    # Stage 5: Show manual items for confirmation (interactive mode)
    if plan["manual_fixes"] and not auto_mode:
        print()
        print(f"--- {len(plan['manual_fixes'])} 个结构类问题待确认 ---")
        for i, fix in enumerate(plan["manual_fixes"], 1):
            print(f"  {i}. [{fix['detector']}] {fix['message']}")
            print(f"     建议: {fix.get('suggestion', 'N/A')}")
        print()
        print("请逐项确认后执行（或使用 --auto 跳过确认）")

    # Stage 6: Learner
    log_path = save_execution_log(str(Path(file_path).parent))

    file_info = {
        "path": file_path,
        "size_kb": tree["file_size_kb"],
        "total_lines": tree["total_lines"],
    }

    with open(log_path, encoding="utf-8") as f:
        log = json.load(f)

    learner.learn(log, file_info)
    print()
    print(f"学习数据已更新（累计运行 {learner.get_stats()['run_count']} 次）")

    # Output final summary
    print()
    print("=" * 60)
    print("  执行完成")
    print("=" * 60)

    summary = plan["summary"]
    print(f"  Bug 修复:    {len(plan['auto_fixes'])} 项")
    print(f"  结构待确认:  {len(plan['manual_fixes'])} 项")
    print(f"  优化建议:    {len(plan['suggestions'])} 项")


if __name__ == "__main__":
    main()
