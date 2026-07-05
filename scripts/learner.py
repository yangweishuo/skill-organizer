"""
自进化引擎

输入：执行日志（由 executor.py 产出）
输出：更新后的 rules/memory.json

三种进化行为：
1. 权重调整：根据命中率调整检测器优先级
2. 规则追加：将新模式写入 custom_rules
3. 策略自适应：文件 >300KB 分段分析；连续 3 次假阳性休眠
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# 默认检测器权重
DEFAULT_WEIGHTS = {
    "D1": 0.90,
    "D2": 0.70,
    "D3": 0.85,
    "D4": 0.50,
    "D5": 0.40,
    "D6": 0.60,
    "D7": 0.80,
    "D8": 0.30,
    "D9": 0.35,
    "D10": 0.95,
}

# 文件大小阈值（KB）：超过此值启用分段分析
LARGE_FILE_THRESHOLD = 300

# 分段分析每段行数
CHUNK_LINES = 5000

# 休眠阈值：连续假阳性次数
DORMANT_THRESHOLD = 3

# 降噪阈值：命中率低于此值降低权重
NOISE_THRESHOLD = 0.30


class Learner:
    """自进化学习引擎。"""

    def __init__(self, rules_dir: str):
        self.rules_dir = Path(rules_dir)
        self.memory_path = self.rules_dir / "memory.json"
        self.memory = self._load_memory()

    def _load_memory(self) -> dict:
        """加载学习数据。"""
        if self.memory_path.exists():
            return json.loads(self.memory_path.read_text(encoding="utf-8"))

        # Initialize fresh memory
        detectors = {}
        for d_id, weight in DEFAULT_WEIGHTS.items():
            detectors[d_id] = {
                "weight": weight,
                "hits": 0,
                "false_positives": 0,
                "dormant": False,
            }

        return {
            "version": "1.0",
            "run_count": 0,
            "detectors": detectors,
            "custom_rules": [],
            "file_history": [],
            "adaptive_strategies": {
                "large_file_chunking": True,
                "chunk_lines": CHUNK_LINES,
            },
        }

    def learn(self, execution_summary: dict, file_info: dict) -> dict:
        """从一次执行中学习。

        Args:
            execution_summary: executor 产出的执行摘要
            file_info: {"path": str, "size_kb": float, "total_lines": int}

        Returns:
            更新后的 memory
        """
        self.memory["run_count"] += 1

        # Record file history
        self.memory["file_history"].append({
            "path": file_info["path"],
            "size_kb": file_info["size_kb"],
            "total_lines": file_info["total_lines"],
            "timestamp": datetime.now().isoformat(),
            "operations": execution_summary.get("total_operations", 0),
            "successful": execution_summary.get("successful", 0),
            "failed": execution_summary.get("failed", 0),
        })

        # Weight adjustment from execution results
        details = execution_summary.get("details", [])
        detector_stats: dict[str, dict] = {}

        for op in details:
            d_id = op.get("detector", "")
            if d_id not in detector_stats:
                detector_stats[d_id] = {"hits": 0, "total": 0}
            detector_stats[d_id]["total"] += 1
            if op.get("success"):
                detector_stats[d_id]["hits"] += 1

        for d_id, stats in detector_stats.items():
            if d_id in self.memory["detectors"]:
                detector = self.memory["detectors"][d_id]
                hit_rate = stats["hits"] / stats["total"] if stats["total"] > 0 else 0

                # Update hit/false_positive counts
                detector["hits"] = detector.get("hits", 0) + stats["hits"]
                detector["false_positives"] = (
                    detector.get("false_positives", 0) + stats["total"] - stats["hits"]
                )

                # Weight adjustment
                if hit_rate < NOISE_THRESHOLD:
                    detector["weight"] = max(0.1, detector["weight"] * 0.8)
                else:
                    detector["weight"] = min(1.0, detector["weight"] * 1.05 + hit_rate * 0.1)

                # Dormant check: >3 consecutive false positives
                consecutive_fp = detector.get("consecutive_fp", 0)
                if stats["total"] > 0 and stats["hits"] == 0:
                    consecutive_fp += 1
                else:
                    consecutive_fp = 0
                detector["consecutive_fp"] = consecutive_fp
                if consecutive_fp >= DORMANT_THRESHOLD:
                    detector["dormant"] = True

        # Adaptive strategy: large file detection
        if file_info["size_kb"] > LARGE_FILE_THRESHOLD:
            self.memory["adaptive_strategies"]["large_file_chunking"] = True

        self._save_memory()
        return self.memory

    def add_custom_rule(self, detector: str, pattern: str, description: str) -> dict:
        """追加自定义检测规则。

        当用户手动修正了自动检测未发现的问题时调用。
        """
        rule = {
            "detector": detector,
            "pattern": pattern,
            "description": description,
            "added": datetime.now().isoformat(),
            "hit_count": 0,
        }
        self.memory["custom_rules"].append(rule)
        self._save_memory()
        return self.memory

    def get_active_detectors(self) -> list[str]:
        """获取当前未休眠的检测器列表，按权重排序。"""
        active = [
            (d_id, info["weight"])
            for d_id, info in self.memory["detectors"].items()
            if not info.get("dormant", False)
        ]
        active.sort(key=lambda x: -x[1])
        return [d_id for d_id, _ in active]

    def get_strategy(self) -> dict:
        """获取当前自适应策略。"""
        return self.memory.get("adaptive_strategies", {})

    def get_stats(self) -> dict:
        """获取学习统计摘要。"""
        return {
            "run_count": self.memory["run_count"],
            "detectors": {
                d_id: {
                    "weight": round(info["weight"], 2),
                    "hits": info["hits"],
                    "false_positives": info["false_positives"],
                    "dormant": info.get("dormant", False),
                }
                for d_id, info in self.memory["detectors"].items()
            },
            "custom_rules_count": len(self.memory["custom_rules"]),
            "files_processed": len(self.memory["file_history"]),
        }

    def _save_memory(self) -> None:
        """持久化学习数据。"""
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory_path.write_text(
            json.dumps(self.memory, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python learner.py --learn <execution_log.json> <file_path>")
        print("  python learner.py --stats")
        print("  python learner.py --add-rule <detector> <pattern> <description>")
        sys.exit(1)

    # Determine rules dir relative to this script
    script_dir = Path(__file__).parent.parent
    rules_dir = script_dir / "rules"
    learner = Learner(str(rules_dir))

    if sys.argv[1] == "--stats":
        print(json.dumps(learner.get_stats(), ensure_ascii=False, indent=2))

    elif sys.argv[1] == "--learn":
        log_path = sys.argv[2]
        file_path = sys.argv[3]

        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)

        file_info = {
            "path": file_path,
            "size_kb": round(Path(file_path).stat().st_size / 1024, 1),
            "total_lines": len(Path(file_path).read_text(encoding="utf-8").split("\n")),
        }

        result = learner.learn(log, file_info)
        print(json.dumps(learner.get_stats(), ensure_ascii=False, indent=2))

    elif sys.argv[1] == "--add-rule":
        detector = sys.argv[2]
        pattern = sys.argv[3]
        description = sys.argv[4] if len(sys.argv) > 4 else ""
        result = learner.add_custom_rule(detector, pattern, description)
        print(json.dumps(result, ensure_ascii=False, indent=2))
