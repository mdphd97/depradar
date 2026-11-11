"""Base utilities for DepRadar scanners."""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Tuple

def format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024 * 1024 * 1024:
        return f"{bytes_val / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_val / (1024 * 1024 * 1024):.2f} GB"

def get_dir_size_and_mtime(path_obj: Path, max_depth: int = 4) -> Tuple[int, float]:
    if not path_obj.exists():
        return 0, time.time()
    total_size = 0
    latest_mtime = path_obj.stat().st_mtime
    try:
        if path_obj.is_file():
            return path_obj.stat().st_size, latest_mtime
        
        # Traverse with controlled depth to remain high performance
        root_depth = len(path_obj.parts)
        for root, dirs, files in os.walk(path_obj):
            cur_depth = len(Path(root).parts) - root_depth
            if cur_depth >= max_depth:
                dirs.clear()
                continue
            dirs[:] = [d for d in dirs if d not in [".git", "node_modules", ".cache", "__pycache__"]]
            for f in files:
                fp = Path(root) / f
                try:
                    st = fp.stat()
                    total_size += st.st_size
                    if st.st_mtime > latest_mtime:
                        latest_mtime = st.st_mtime
                except (PermissionError, FileNotFoundError):
                    pass
    except Exception:
        pass
    return total_size, latest_mtime

def calculate_age_and_status(mtime_timestamp: float) -> Tuple[str, int, str]:
    now = datetime.now()
    dt = datetime.fromtimestamp(mtime_timestamp)
    days = max(0, (now - dt).days)
    date_str = dt.strftime("%Y-%m-%d")
    if days < 14:
        status = "active"
    elif days < 30:
        status = "inactive"
    else:
        status = "stale"
    return date_str, days, status

def size_to_radius(bytes_val: int) -> float:
    # Scale from 4 to 28 for node rendering
    mb = bytes_val / (1024 * 1024)
    if mb < 1:
        return 4.0
    elif mb < 10:
        return 6.0
    elif mb < 100:
        return 10.0
    elif mb < 500:
        return 15.0
    elif mb < 1000:
        return 20.0
    else:
        return 26.0
