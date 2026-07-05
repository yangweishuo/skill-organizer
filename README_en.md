# skill-organizer: Intelligent SKILL.md Optimizer

## Overview

`skill-organizer` is a **meta-skill** — it operates on the SKILL.md files of other skills, systematizing battle-tested optimization techniques into a reusable detect-and-repair pipeline. After each run, it adjusts detection strategies based on execution results, enabling continuous self-evolution.

### Core Philosophy

SKILL.md files bloat with each feature iteration (e.g. web-presentation-video reached 381 KB / 14,675 lines). Manually maintaining section structure, version numbering, and heading hierarchies is error-prone. skill-organizer automates this maintenance work, freeing humans from tedious structural checks.

## Background

### Problem Discovery

While iterating on web-presentation-video's SKILL.md, four typical issue categories were diagnosed:

| # | Problem | Severity | Example |
|---|---------|----------|---------|
| 1 | Version numbering drift | Critical | `v6.52.2` not updated when editing section v6.53 |
| 2 | Module fragmentation | Major | v6.53 (Douyin rules) and v6.54 (Douyin mid-length) separated by ~7,700 unrelated lines |
| 3 | Heading level conflicts | Major | `## Chapter I` inside sub-modules conflicting with top-level chapters |
| 4 | Description bloat | Minor | YAML description linearly stacking version numbers, up to 700 characters |

After manually fixing these issues, it became clear this maintenance scenario would recur frequently as the number of skills grows. Hence the decision to crystallize the repair workflow into a self-evolving meta-skill.

## Architecture

### Pipeline

```
SKILL.md → Parser → Structure Tree (JSON)
                       ↓
            10 Detectors (parallel scan) → Issue List (3 severity levels)
                                                ↓
                                      Planner → Repair Plan (auto/manual split)
                                                    ↓
                                         Executor → Repaired file + execution log
                                                        ↓
                                              Learner → Updated weights + new patterns
```

### Module Responsibilities

| Module | Input | Output | Core Logic |
|--------|-------|--------|------------|
| **Parser** | Raw SKILL.md text | Structure tree JSON | Regex extraction of headings, YAML, code blocks, version refs, internal refs |
| **Detector** | Structure tree JSON | Issue list | 10 independent detectors in parallel, each issue tagged with severity, fix type, suggestion |
| **Planner** | Issue list | Repair plan | Three-tier routing: Bug → auto / Structure → confirm / Optimize → report |
| **Executor** | Plan + source file | Repaired file + log | `old_str`/`new_str` exact-match replacement, auto-backup before editing |
| **Learner** | Execution log + file info | Updated rules/weights | Hit-rate-driven weight adjustment, pattern appending, adaptive strategy |

## 10 Detectors

### Bug Level (Auto-fix)

| ID | Detector | Logic | Strategy |
|----|----------|-------|----------|
| **D1** | Version Number Continuity | Extract all version numbers, verify against section context | Correct misplaced numbers |
| **D3** | Heading Level Conflict | Cross-validate Chinese-numbered headings against top-level chapters | Downgrade conflicting `##` to `###` |
| **D7** | Version Consistency | Compare YAML `version` vs max version in content | Update YAML to match content |
| **D10** | YAML Completeness | Check `name`/`description`/`version` field presence | Fill missing fields |

### Structure Level (Requires Confirmation)

| ID | Detector | Logic | Strategy |
|----|----------|-------|----------|
| **D2** | Module Cohesion | Group by topic keywords, detect same-topic sections >500 lines apart | Move sections to same-topic region |
| **D5** | Duplicate Content | Set intersection of lines >50 chars across adjacent sections | Keep one copy, remove duplicates |
| **D6** | Chapter Numbering Consistency | Check Chinese numeral sequence continuity | Flag gaps or jumps |

### Optimize Level (Report Only)

| ID | Detector | Logic | Suggestion |
|----|----------|-------|------------|
| **D4** | Description Brevity | Char count >300 or >5 version refs | Condense to one core sentence |
| **D8** | Code Block Language | Detect ` ``` ` without language tag | Add language tag |
| **D9** | Reference Validity | Extract internal links, verify anchors exist | Fix or remove dead references |

## Hybrid Execution Mode

```
Issue Severity
├─ Bug (D1/D3/D7/D10)   → Auto-fix, no prompt needed
├─ Structure (D2/D5/D6) → Show issue + suggestion, execute after confirmation
└─ Optimize (D4/D8/D9)  → List at end of report, no automatic action
```

## Self-Evolution

### Three Evolution Behaviors

| Behavior | Trigger | Effect |
|----------|---------|--------|
| **Weight Adjustment** | Every run | Boost high-hit detectors; degrade <30% hit-rate ones |
| **Rule Appending** | Manual fix of undetected issue | Append new pattern to corresponding detector |
| **Adaptive Strategy** | Accumulated data thresholds | >300KB → chunked analysis; 3 consecutive false positives → dormant |

## Usage

### CLI

```bash
# Analysis mode (report only, no file changes)
python scripts/main.py <path-to-SKILL.md> --dry-run

# Hybrid mode (default: auto-fix bugs, confirm structural changes)
python scripts/main.py <path-to-SKILL.md>

# Full-auto mode (skip confirmation)
python scripts/main.py <path-to-SKILL.md> --auto

# View learning stats
python scripts/main.py --stats
```

## File Structure

```
skill-organizer/
├── SKILL.md                        # Skill main file
├── scripts/
│   ├── main.py                     # Entry point (pipeline orchestrator)
│   ├── parser.py                   # Structure tree parser
│   ├── detector.py                 # 10-detector engine
│   ├── planner.py                  # Repair plan generator
│   ├── executor.py                 # Repair executor
│   └── learner.py                  # Self-evolution engine
├── rules/
│   ├── memory.json                 # Learning data (weights/hits/dormant state)
│   └── patterns.json               # Detection pattern definitions
└── references/
    └── detection-catalog.md        # Detailed detection rule documentation
```

## Benchmarks

Dry-run analysis on web-presentation-video's SKILL.md (381 KB, 14,675 lines):

| Metric | Value |
|--------|-------|
| Total issues | 117 |
| Bug-level | 1 (D7: version mismatch) |
| Structure-level | 3 (module cohesion / duplicates / chapter gap) |
| Optimize-level | 113 (code block language tags) |
| Analysis time | < 1 second |

## Roadmap

| Version | Goal | Content |
|---------|------|---------|
| v1.0 | Core pipeline operational | 10 detectors + hybrid execution + basic learning |
| v1.1 | Detection accuracy | D1 context algorithm enhancement, false positive reduction |
| v1.2 | Executor enhancement | Batch operations, rollback mechanism |
| v2.0 | Multi-file management | Batch scan `skills/` directory, cross-file reference detection |

