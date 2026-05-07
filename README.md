# Task Workflow V3

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License: MIT">
  <img src="https://img.shields.io/badge/Version-1.0.0-orange" alt="Version: 1.0.0">
</p>

> **解决 AI Agent 产出与用户预期不一致的问题**
> 五步状态机任务管理框架：确认 → 设计 → 执行 → 自检 → 交付

---

## ✨ 特性

- 🎯 **复述确认** — 先对齐理解再动手，避免方向偏差
- 📋 **方案设计** — 确认怎么做再执行，方案阶段不怕改
- 🔧 **严格执行** — 按方案做不偏离，只改用户明确说的部分
- ✅ **交付自检** — 交付前自验，不让用户发现问题
- 📦 **自动交付** — 文档输出后自动发送，不遗漏不等待
- 🔄 **状态回退** — 用户说"改"→回退上一步，灵活调整
- 📊 **事件驱动** — 每个任务唯一ID，状态全程可追溯
- ⚡ **多任务并行** — 同时处理多个任务，互不干扰

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/NickY4ng/task-workflow.git

# 复制到 Hermes skills 目录
cp -r task-workflow ~/.hermes/skills/software-development/
```

### 使用

在 Hermes Agent 中加载 Skill 后，任何派活类请求自动进入五步状态机：

```
[Taskflow: Step 1/5 | Event: 示例任务] 复述确认

航哥，我的理解是：
- 核心任务：xxx
- 执行方案：xxx
- 交付物：xxx

方向对不？
```

用户确认后自动推进到下一步，直到交付完成。

---

## 📁 项目结构

```
task-workflow/
├── SKILL.md                          # Skill 文档（完整规范）
├── scripts/
│   └── taskflow_state_machine.py     # 状态机脚本（核心驱动）
├── docs/
│   ├── verification-burden.md          # 验证负担研究摘要
│   └── checklist.md                  # 自检清单模板
├── examples/                         # 使用示例
└── CHANGELOG.md                      # 版本历史
```

---

## 🏗️ 五步状态机详解

```
┌─────────────┐     触发词/派活      ┌─────────────┐
│  闲聊模式   │ ──────────────────→ │  任务模式   │
│  (正常回复) │                      │ (状态机驱动) │
└─────────────┘                      └──────┬──────┘
       ↑                                    │
       └──────── 任务完成/用户说"结束" ──────┘
```

### Step 1：复述确认 — 对齐理解，不是对齐文字

AI 用自己的话复述需求，用户纠正偏差，循环直到双方理解一致。

### Step 2：方案设计 — 确认怎么做，不是直接做

AI 出方案（流程、结构、关键决策点），用户确认或调整。

### Step 3：执行 — 按方案做，不偏离

严格执行已确认的方案，遇到不确定→回退到方案确认，不自己猜。

### Step 4：自检 — 交付前自己先过一遍

对照方案、需求、约束逐项检查，自己先发现问题。

### Step 5：交付 — 确认完成，不是发了就完

自动发送交付物，用户说"收到"才算完。

---

## 📊 事件驱动管理

每个任务有唯一 ID，全程可追溯：

```json
{
  "event_id": "a1b2c3d4",
  "status": "step_3_execute",
  "requirement": {"original": "帮我写篇文章", "confirmed": "写一篇AI提效文章"},
  "design": {"confirmed": "方案已确认", "template_type": "文档生成类"},
  "process_log": [{"step": "create", "action": "任务创建"}, ...],
  "result": {"output_files": ["文章.md"], "summary": "已完成"}
}
```

---

## 📜 版本历史

参见 [CHANGELOG.md](CHANGELOG.md)

---

## 📄 License

MIT © 2026 NickYang
