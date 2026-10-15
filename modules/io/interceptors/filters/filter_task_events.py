#!/usr/bin/env python3
"""
filter_task_events.py - Detects agent task lifecycles (started, completed, tool calls).
"""
import re
from typing import Optional, Dict, Any

def filter_line(line: str) -> Optional[Dict[str, Any]]:
    if not line:
        return None
    
    if "[task:start]" in line or "Starting task" in line:
        return {
            "event": "agent.task.started",
            "source": "language_server:stdout",
            "data": {"raw": line.strip()}
        }
    elif "[task:done]" in line or "Task completed" in line:
        return {
            "event": "agent.task.completed",
            "source": "language_server:stdout",
            "data": {"raw": line.strip()}
        }
    elif "tool_call:" in line:
        return {
            "event": "agent.tool.executed",
            "source": "language_server:stdout",
            "data": {"raw": line.strip()}
        }
    
    return None
