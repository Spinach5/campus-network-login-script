#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动登录脚本 — 命令行入口。

支持多账号、自动探测 Portal、RSA 密码加密、运营商选择。
"""

import sys
import argparse
from typing import Dict, Optional

from portal import detect_portal, do_login, get_online_user_info
from config import (
    load_users, save_user_index, select_user, auto_detect_user,
    add_portal_to_user_weblist, save_user_portal_info,
)
from crypto import encrypt_password
from log_utils import get_logger

logger = get_logger(__name__)


def main(user_override: Optional[Dict] = None):
    # 1. 探测 Portal（日志已在 detect_portal 内部记录）
    logger.info("开始登录流程")
    try:
        portal_base, query_string, exponent, modulus, mac = detect_portal()
    except Exception as e:
        logger.error("Portal 探测失败: %s", e)
        sys.exit(1)

    # 2. 确定用户
    if user_override:
        user = user_override
    else:
        try:
            users = load_users()
        except Exception as e:
            logger.error("加载用户列表失败: %s", e)
            sys.exit(1)
        if not users:
            logger.error("用户列表为空")
            sys.exit(1)

        auto_user = auto_detect_user(users, portal_base)
        if auto_user:
            logger.info("自动识别用户: %s (Portal: %s)", auto_user.get("name"), portal_base)
            user = auto_user
        else:
            user = select_user(users)

    username = user["account"]
    plain_pwd = user["password"]
    service = user.get("server", "LT")
    logger.info("已选择: %s (%s) 服务: %s", user.get("name", username), username, service)

    # 3. RSA 加密密码
    try:
        encrypted_pwd = encrypt_password(plain_pwd, mac, exponent, modulus)
    except Exception as e:
        logger.error("密码加密失败: %s", e)
        sys.exit(1)

    # 4. 发送登录请求
    logger.info("执行登录请求...")
    try:
        result = do_login(portal_base, username, encrypted_pwd, service, query_string)
    except Exception as e:
        logger.error("登录请求失败: %s", e)
        sys.exit(1)

    # 5. 处理认证结果
    if result.get("result") != "success":
        error_msg = result.get("message", "未知错误")
        logger.error("认证失败: %s", error_msg)
        sys.exit(1)

    logger.info("✅ 认证成功!")
    user_index = result.get("userIndex")
    keepalive_interval = result.get("keepaliveInterval")
    logger.info("userIndex: %s, keepaliveInterval: %s 秒", user_index, keepalive_interval)

    # 6. 保存 Portal 地址和用户信息到本地配置
    if not user_override:
        add_portal_to_user_weblist(username, portal_base)
        save_user_index(username, user_index)

        online_info = get_online_user_info(portal_base, user_index)
        if online_info:
            save_user_portal_info(username, online_info)
            logger.info("已更新用户信息: %s / %s / %s",
                        online_info.get("userName"),
                        online_info.get("realServiceName"),
                        online_info.get("userPackage"))

    return portal_base, result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="校园网自动登录")
    parser.add_argument("-cli", action="store_true", help="命令行交互模式")
    parser.add_argument("-u", "--username", help="学号/账号")
    parser.add_argument("-p", "--password", help="密码")
    parser.add_argument("-s", "--server", default="LT", help="运营商代码 (LT/YD/DX)，默认 LT")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.username and args.password:
        user = {
            "name": args.username,
            "account": args.username,
            "password": args.password,
            "server": args.server,
        }
        main(user_override=user)
    elif args.cli:
        main()
    else:
        from gui import launch_gui
        launch_gui()
