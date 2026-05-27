#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志工具模块。

提供日期分目录的日志文件输出 + 控制台输出，以及密码掩码等辅助函数。
"""

import logging
import os
from datetime import datetime

_log_configured = False
_root_logger = None


def _get_log_dir() -> str:
    """返回日志目录路径：py/{YYYY-MM-DD}-logs/"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "py", f"{date_str}-logs")


def _configure():
    """配置根 logger（仅首次调用生效）。"""
    global _log_configured, _root_logger

    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%H-%M-%S-%f")
    log_file = os.path.join(log_dir, f"login-{timestamp}.log")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 文件 handler：DEBUG 及以上全记录
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] %(name)s.%(funcName)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # 控制台 handler：INFO 及以上，简洁格式
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    root.addHandler(ch)

    _log_configured = True
    _root_logger = root


def get_logger(name: str) -> logging.Logger:
    """获取指定 name 的 logger，首次调用时自动配置 handlers。"""
    if not _log_configured:
        _configure()
    return logging.getLogger(name)


def mask_password(pwd: str) -> str:
    """返回掩码后的密码字符串，仅保留前 2 个字符。"""
    if not pwd:
        return "<empty>"
    return pwd[:2] + "****"
