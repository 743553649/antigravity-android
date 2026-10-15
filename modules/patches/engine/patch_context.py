"""
patch_context.py - Encapsulates session configuration and execution flags.
"""
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class PatchContext:
    target_path: str
    dry_run: bool = False
    verify: bool = False
    allow_missing: bool = False
    log_messages: list = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)

    def log(self, msg: str):
        self.log_messages.append(msg)
        print(f"  {msg}")
