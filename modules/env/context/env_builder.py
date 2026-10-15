import os
import json
from typing import Dict, Any

try:
    from . import path_resolver
except ImportError:
    import path_resolver

SPEC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spec")

def build_process_env(custom_spec_dir: str = None, extra_env: Dict[str, str] = None, app_id: str = None) -> Dict[str, str]:
    spec_dir = custom_spec_dir or SPEC_DIR
    paths = path_resolver.load_paths(os.path.join(spec_dir, "paths.json"), app_id=app_id)
    
    with open(os.path.join(spec_dir, "env_vars.json"), "r", encoding="utf-8") as f:
        spec = json.load(f)

    env = dict(spec.get("static", {}))
    app_root = paths["app_root"]
    env["HOME"] = app_root
    env["TMPDIR"] = paths["cache"]
    pkg_id = app_id or path_resolver.get_application_id()
    env["AGY_APPLICATION_ID"] = pkg_id

    # Build PATH
    path_entries = [p.format(**paths) for p in spec.get("path_order", [])]
    env["PATH"] = ":".join(path_entries)

    # Build LD_LIBRARY_PATH
    ld_entries = [p.format(**paths) for p in spec.get("ld_library_paths", []) if os.path.isdir(p.format(**paths))]
    if ld_entries:
        env["LD_LIBRARY_PATH"] = ":".join(ld_entries)

    if extra_env:
        env.update(extra_env)

    return env

