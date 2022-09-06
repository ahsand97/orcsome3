import re
import subprocess
from typing import Dict, List, Pattern, Tuple

_re_cache: Dict[str, Pattern[str]] = {}


def match_string(pattern: str, data: str) -> bool:
    if not pattern in _re_cache.keys():
        _re_cache[pattern] = re.compile(pattern=pattern)
    pattern_ = _re_cache[pattern]

    return bool(re.search(pattern=pattern_, string=data))


def get_compiler_args(*libraries: str) -> Tuple[List[str], List[str]]:
    cmd_cflags: List[str] = ["pkg-config", "--cflags"]
    cmd_cflags.extend(libraries)
    process_cflags: subprocess.CompletedProcess = subprocess.run(
        args=cmd_cflags, capture_output=True, text=True, encoding="utf-8"
    )
    result_cflags: List[str] = [x for x in process_cflags.stdout.replace("\n", "").split(sep=" ") if len(x.strip())]

    cmd_libs: List[str] = ["pkg-config", "--libs"]
    cmd_libs.extend(libraries)
    process_libs: subprocess.CompletedProcess = subprocess.run(
        args=cmd_libs, capture_output=True, text=True, encoding="utf-8"
    )
    result_libs: List[str] = [
        x.replace("-l", "") for x in process_libs.stdout.replace("\n", "").split(sep=" ") if len(x.strip())
    ]

    return result_cflags, result_libs
