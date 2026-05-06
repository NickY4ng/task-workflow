import json
import uuid
import os
import re
import subprocess
from datetime import datetime

EVENTS_DIR = os.path.expanduser("~/.hermes/taskflow/events")
LOGS_DIR = os.path.expanduser("~/.hermes/taskflow/logs")

# 中文事件名校验：禁止纯英文+数字，必须含中文字符或中文描述
def validate_event_name(name):
    """校验事件名是否为中文"""
    if not name:
        return False, "事件名不能为空"
    # 检查是否含中文字符
    has_chinese = bool(re.search(r'[\u4e00-\u9fff]', name))
    # 检查是否全是英文+数字+下划线（禁止）
    is_english_only = bool(re.match(r'^[a-zA-Z0-9_]+$', name))
    if is_english_only:
        return False, f"事件名'{name}'为纯英文，必须用中文"
    if not has_chinese:
        return False, f"事件名'{name}'不含中文，请用中文描述"
    return True, "OK"

# 话题切换检测：判断用户输入是否与当前任务相关
def detect_topic_switch(event, user_input):
    """检测用户是否切换话题"""
    if not event or not user_input:
        return False
    # 获取当前任务关键词
    req = event.get("requirement", {})
    keywords = []
    if req.get("original"):
        keywords.extend(req["original"].split())
    if req.get("confirmed"):
        keywords.extend(req["confirmed"].split())
    
    # 简单判断：输入是否含任务关键词
    input_words = user_input.split()
    has_keyword = any(kw in input_words for kw in keywords if len(kw) > 2)
    
    # 如果输入很短（<5字）或不含关键词，可能是切换话题
    if len(user_input) < 5 or not has_keyword:
        return True
    return False

# 自动发文件到飞书
def auto_send_file(file_path):
    """自动调用 feishu-file-send 发文件"""
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}
    
    # 调用 feishu-file-send skill 脚本
    feishu_script = os.path.expanduser("~/.hermes/skills/productivity/feishu-file-send/scripts/send.sh")
    if os.path.exists(feishu_script):
        result = subprocess.run(
            ["bash", feishu_script, file_path],
            capture_output=True, text=True
        )
        return {"sent": result.returncode == 0, "output": result.stdout, "error": result.stderr}
    
    # 如果没有脚本，记录待发送
    return {"pending": True, "file_path": file_path, "note": "feishu-file-send 脚本未找到，需手动发送"}

# 严格 patch：只改用户明确提到的部分
def strict_patch(event_id, old_string, new_string, file_path):
    """严格替换，只改用户说的部分"""
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # 检查 old_string 是否唯一存在
    count = content.count(old_string)
    if count == 0:
        return {"error": f"找不到匹配文本: {old_string[:50]}..."}
    if count > 1:
        return {"error": f"匹配文本不唯一（出现{count}次），请提供更精确的上下文"}
    
    # 执行替换
    new_content = content.replace(old_string, new_string, 1)
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    return {"success": True, "file_path": file_path, "replaced": old_string[:50]}

# 状态定义
STATES = [
    "idle",              # 初始
    "step_1_confirm",    # 复述确认
    "step_2_design",     # 方案设计
    "step_3_execute",    # 执行
    "step_4_verify",     # 自检校验
    "step_5_deliver",    # 交付
    "complete",          # 完成
    "paused",            # 暂停（用户说"先这样"）
    "aborted"            # 中止（用户说"算了"）
]

# 状态流转规则
TRANSITIONS = {
    "idle": {"start": "step_1_confirm"},
    "step_1_confirm": {
        "confirm": "step_2_design",
        "modify": "step_1_confirm",  # 用户补充/修改需求
        "abort": "aborted"
    },
    "step_2_design": {
        "confirm": "step_3_execute",
        "modify": "step_2_design",
        "abort": "aborted"
    },
    "step_3_execute": {
        "done": "step_4_verify",
        "pause": "paused",
        "abort": "aborted"
    },
    "step_4_verify": {
        "pass": "step_5_deliver",
        "fail": "step_3_execute",  # 自检不过，回执行
        "abort": "aborted"
    },
    "step_5_deliver": {
        "confirm": "complete",
        "modify": "step_3_execute",  # 用户要改，回执行
        "abort": "aborted"
    },
    "paused": {
        "resume": "step_3_execute",
        "abort": "aborted"
    }
}

def _ensure_dirs():
    os.makedirs(EVENTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

def _event_path(event_id):
    return os.path.join(EVENTS_DIR, f"{event_id}.json")

def _log_path(event_id):
    return os.path.join(LOGS_DIR, f"{event_id}.log")

def _load_event(event_id):
    path = _event_path(event_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

def _save_event(event):
    _ensure_dirs()
    path = _event_path(event["event_id"])
    event["updated_at"] = datetime.now().isoformat()
    with open(path, "w") as f:
        json.dump(event, f, ensure_ascii=False, indent=2)

def _append_log(event_id, message):
    _ensure_dirs()
    path = _log_path(event_id)
    timestamp = datetime.now().isoformat()
    with open(path, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

def create_event(requirement, user_input, mode="standard"):
    """创建新任务事件"""
    _ensure_dirs()
    event_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    
    # 中文事件名校验
    valid, msg = validate_event_name(requirement)
    if not valid:
        return {"error": msg, "event_id": None, "status": "error"}
    
    event = {
        "event_id": event_id,
        "status": "step_1_confirm",
        "mode": mode,  # standard / quick / full
        "created_at": now,
        "updated_at": now,
        "requirement": {
            "original": user_input,
            "confirmed": None,  # 确认后的摘要
            "parsed": {}  # 解析后的字段
        },
        "process_log": [
            {"step": "create", "time": now, "action": "任务创建", "detail": requirement}
        ],
        "result": {
            "output_files": [],
            "summary": None,
            "checklist": {}
        },
        "feedback": [],
        "current_step": 1,
        "total_steps": 5
    }
    
    _save_event(event)
    _append_log(event_id, f"[CREATE] 任务创建 | 模式: {mode} | 需求: {requirement}")
    
    return {
        "event_id": event_id,
        "status": "step_1_confirm",
        "message": f"[Taskflow: Step 1/5 | Event: {event.get('event_name', event_id)}] 复述确认",
        "display": f"任务已创建 ({event_id})\n当前状态: [Taskflow: Step 1/5 | Event: {event.get('event_name', event_id)}] - 复述确认\n\n请确认以下理解是否正确，或补充修改：\n\n{requirement}"
    }

def process_step(event_id, user_input, action=None):
    """处理用户输入，推进状态"""
    event = _load_event(event_id)
    if not event:
        return {"error": f"事件不存在: {event_id}"}
    
    # 话题切换检测
    if detect_topic_switch(event, user_input):
        return {
            "event_id": event_id,
            "status": event["status"],
            "current_step": event["current_step"],
            "total_steps": event["total_steps"],
            "message": f"[Taskflow: Step {event['current_step']}/{event['total_steps']} | Event: {event.get('event_name', '未命名')}] 检测到可能切换话题",
            "topic_switch_detected": True,
            "suggestion": "当前任务是否暂停？还是说'继续'推进？",
            "display": f"""
当前还在处理：{event['requirement']['confirmed'] or event['requirement']['original']}

您刚才说的好像和当前任务无关？

请选择：
- "继续" → 继续当前任务
- "暂停" → 暂停当前任务，去做其他事
- "结束" → 结束当前任务
"""
        }
    
    current_state = event["status"]
    
    # 如果用户说"结束"/"先这样"/"聊别的" → 暂停
    if user_input in ["结束", "先这样", "聊别的", "随便聊聊", "算了"]:
        if current_state in ["step_3_execute", "step_4_verify", "step_5_deliver"]:
            event["status"] = "paused"
            _save_event(event)
            _append_log(event_id, f"[PAUSE] 用户暂停 | 输入: {user_input}")
            return {
                "event_id": event_id,
                "status": "paused",
                "message": f"[Taskflow: Paused | Event: {event.get('event_name', event_id)}] 任务已暂停",
                "display": "任务已暂停。发送「继续」恢复，或发送「结束」终止。"
            }
        elif user_input == "算了":
            event["status"] = "aborted"
            _save_event(event)
            _append_log(event_id, f"[ABORT] 用户中止 | 输入: {user_input}")
            return {
                "event_id": event_id,
                "status": "aborted",
                "message": f"[Taskflow: Aborted | Event: {event.get('event_name', event_id)}] 任务已中止",
                "display": "任务已中止。"
            }
    
    # 如果用户说"继续" → 恢复
    if user_input == "继续" and current_state == "paused":
        event["status"] = "step_3_execute"
        _save_event(event)
        _append_log(event_id, f"[RESUME] 用户恢复 | 输入: {user_input}")
        return {
            "event_id": event_id,
            "status": "step_3_execute",
            "message": f"[Taskflow: Step 3/5 | Event: {event.get('event_name', event_id)}] 执行中",
            "display": "任务已恢复，继续执行..."
        }
    
    # 状态流转
    allowed = TRANSITIONS.get(current_state, {})
    
    # 如果没有明确 action，根据用户输入推断
    if not action:
        if user_input in ["对", "是的", "没错", "确认", "行", "好"]:
            action = "confirm"
        elif user_input in ["改", "不对", "补充", "再想想"]:
            action = "modify"
        elif user_input in ["停", "算了", "不要了"]:
            action = "abort"
        elif current_state == "step_3_execute":
            action = "done"  # 执行完成，进入自检
        else:
            # 默认：记录反馈，不推进
            _append_log(event_id, f"[INPUT] 用户输入 | 状态: {current_state} | 输入: {user_input}")
            return {
                "event_id": event_id,
                "status": current_state,
                "message": f"[Taskflow: Step {event['current_step']}/5 | Event: {event.get('event_name', event_id)}] 等待确认",
                "display": f"当前状态: Step {event['current_step']}/5\n请确认或修改。"
            }
    
    # 检查 action 是否允许
    if action not in allowed:
        _append_log(event_id, f"[REJECT] 非法流转 | 状态: {current_state} | action: {action} | 输入: {user_input}")
        return {
            "event_id": event_id,
            "status": current_state,
            "message": f"[Taskflow: Step {event['current_step']}/5 | Event: {event.get('event_name', event_id)}] 非法操作",
            "display": f"当前状态: {current_state}\n无法执行「{action}」。\n允许的操作: {', '.join(allowed.keys())}"
        }
    
    # 执行流转
    new_state = allowed[action]
    event["status"] = new_state
    
    # 更新当前步骤数
    step_map = {
        "step_1_confirm": 1,
        "step_2_design": 2,
        "step_3_execute": 3,
        "step_4_verify": 4,
        "step_5_deliver": 5,
        "complete": 5,
        "paused": event.get("current_step", 3),
        "aborted": event.get("current_step", 3)
    }
    event["current_step"] = step_map.get(new_state, 1)
    
    # 记录过程
    event["process_log"].append({
        "step": new_state,
        "time": datetime.now().isoformat(),
        "action": action,
        "detail": user_input
    })
    
    # 记录反馈
    if action == "modify":
        event["feedback"].append({
            "time": datetime.now().isoformat(),
            "type": "modify",
            "content": user_input
        })
    
    _save_event(event)
    _append_log(event_id, f"[TRANSITION] {current_state} → {new_state} | action: {action} | 输入: {user_input}")
    
    # 构建返回消息
    step_names = {
        "step_1_confirm": "复述确认",
        "step_2_design": "方案设计",
        "step_3_execute": "执行",
        "step_4_verify": "自检校验",
        "step_5_deliver": "交付",
        "complete": "完成",
        "paused": "暂停",
        "aborted": "中止"
    }
    
    return {
        "event_id": event_id,
        "status": new_state,
        "message": f"[Taskflow: Step {event['current_step']}/5 | Event: {event.get('event_name', event_id)}] {step_names.get(new_state, new_state)}",
        "display": f"状态更新: {current_state} → {new_state}\n当前: [Taskflow: Step {event['current_step']}/5 | Event: {event.get('event_name', event_id)}] - {step_names.get(new_state, new_state)}"
    }

def update_requirement(event_id, confirmed_requirement, parsed=None):
    """更新确认后的需求"""
    event = _load_event(event_id)
    if not event:
        return {"error": f"事件不存在: {event_id}"}
    
    event["requirement"]["confirmed"] = confirmed_requirement
    if parsed:
        event["requirement"]["parsed"] = parsed
    
    _save_event(event)
    _append_log(event_id, f"[REQUIREMENT] 需求确认 | 内容: {confirmed_requirement}")
    
    return {"status": "ok", "event_id": event_id}

def log_process(event_id, action, detail=""):
    """记录过程日志"""
    event = _load_event(event_id)
    if not event:
        return {"error": f"事件不存在: {event_id}"}
    
    event["process_log"].append({
        "step": event["status"],
        "time": datetime.now().isoformat(),
        "action": action,
        "detail": detail
    })
    
    _save_event(event)
    _append_log(event_id, f"[PROCESS] {action} | {detail}")
    
    return {"status": "ok"}

def update_result(event_id, output_files=None, summary=None, checklist=None):
    """更新结果"""
    event = _load_event(event_id)
    if not event:
        return {"error": f"事件不存在: {event_id}"}
    
    if output_files:
        event["result"]["output_files"].extend(output_files)
    if summary:
        event["result"]["summary"] = summary
    if checklist:
        event["result"]["checklist"] = checklist
    
    _save_event(event)
    _append_log(event_id, f"[RESULT] 结果更新 | 文件: {output_files} | 摘要: {summary}")
    
    return {"status": "ok"}

def get_status(event_id):
    """获取事件状态"""
    event = _load_event(event_id)
    if not event:
        return {"error": f"事件不存在: {event_id}"}
    
    return {
        "event_id": event_id,
        "status": event["status"],
        "current_step": event["current_step"],
        "total_steps": event["total_steps"],
        "mode": event["mode"],
        "created_at": event["created_at"],
        "updated_at": event["updated_at"],
        "requirement_confirmed": event["requirement"]["confirmed"] is not None,
        "result_count": len(event["result"]["output_files"]),
        "feedback_count": len(event["feedback"])
    }

def list_events(status=None, limit=10):
    """列出事件"""
    _ensure_dirs()
    events = []
    
    for filename in sorted(os.listdir(EVENTS_DIR), reverse=True):
        if filename.endswith(".json"):
            with open(os.path.join(EVENTS_DIR, filename), "r") as f:
                event = json.load(f)
                if status is None or event["status"] == status:
                    events.append({
                        "event_id": event["event_id"],
                        "status": event["status"],
                        "current_step": event["current_step"],
                        "created_at": event["created_at"],
                        "requirement_preview": event["requirement"]["original"][:50]
                    })
    
    return events[:limit]

def generate_report(event_id):
    """生成任务报告"""
    event = _load_event(event_id)
    if not event:
        return {"error": f"事件不存在: {event_id}"}
    
    lines = []
    lines.append(f"# 任务报告: {event_id}")
    lines.append("")
    lines.append(f"**状态**: {event['status']} | **步骤**: {event['current_step']}/{event['total_steps']}")
    lines.append(f"**创建**: {event['created_at']} | **更新**: {event['updated_at']}")
    lines.append("")
    
    lines.append("## 需求")
    lines.append(f"- 原始: {event['requirement']['original']}")
    if event['requirement']['confirmed']:
        lines.append(f"- 确认: {event['requirement']['confirmed']}")
    lines.append("")
    
    lines.append("## 过程")
    for log in event['process_log']:
        lines.append(f"- [{log['time']}] {log['action']}: {log['detail']}")
    lines.append("")
    
    if event['feedback']:
        lines.append("## 反馈")
        for fb in event['feedback']:
            lines.append(f"- [{fb['time']}] {fb['type']}: {fb['content']}")
        lines.append("")
    
    if event['result']['output_files']:
        lines.append("## 结果")
        for f in event['result']['output_files']:
            lines.append(f"- {f}")
        if event['result']['summary']:
            lines.append(f"\n摘要: {event['result']['summary']}")
        lines.append("")
    
    return "\n".join(lines)

# 命令行接口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python taskflow_state_machine.py <命令> [参数]")
        print("命令: create, step, status, list, report, log, update_req, update_result")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        req = sys.argv[2] if len(sys.argv) > 2 else ""
        user_input = sys.argv[3] if len(sys.argv) > 3 else ""
        mode = sys.argv[4] if len(sys.argv) > 4 else "standard"
        print(json.dumps(create_event(req, user_input, mode), ensure_ascii=False))
    elif cmd == "step":
        event_id = sys.argv[2]
        user_input = sys.argv[3] if len(sys.argv) > 3 else ""
        action = sys.argv[4] if len(sys.argv) > 4 else None
        print(json.dumps(process_step(event_id, user_input, action), ensure_ascii=False))
    elif cmd == "status":
        event_id = sys.argv[2]
        print(json.dumps(get_status(event_id), ensure_ascii=False))
    elif cmd == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(list_events(status), ensure_ascii=False))
    elif cmd == "report":
        event_id = sys.argv[2]
        print(generate_report(event_id))
    elif cmd == "log":
        event_id = sys.argv[2]
        action = sys.argv[3] if len(sys.argv) > 3 else ""
        detail = sys.argv[4] if len(sys.argv) > 4 else ""
        print(json.dumps(log_process(event_id, action, detail), ensure_ascii=False))
    elif cmd == "update_req":
        event_id = sys.argv[2]
        req = sys.argv[3] if len(sys.argv) > 3 else ""
        print(json.dumps(update_requirement(event_id, req), ensure_ascii=False))
    elif cmd == "update_result":
        event_id = sys.argv[2]
        files = sys.argv[3].split(",") if len(sys.argv) > 3 else []
        summary = sys.argv[4] if len(sys.argv) > 4 else None
        print(json.dumps(update_result(event_id, files, summary), ensure_ascii=False))
    else:
        print(f"未知命令: {cmd}")