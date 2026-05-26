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


def main(user_override: Optional[Dict] = None):
    # 1. 探测 Portal
    print("[*] 正在探测 Portal 认证地址...")
    try:
        portal_base, query_string, exponent, modulus, mac = detect_portal()
        print(f"[*] Portal 基础地址: {portal_base}")
        print(f"[+] 公钥获取成功")
        print(f"    exponent: {exponent}")
        print(f"    modulus: {modulus[:40]}...")
        print(f"[*] 使用 MAC: {mac}")
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    # 2. 确定用户
    if user_override:
        user = user_override
    else:
        try:
            users = load_users()
        except Exception as e:
            print(f"❌ 加载用户列表失败: {e}")
            sys.exit(1)
        if not users:
            print("❌ 用户列表为空")
            sys.exit(1)

        auto_user = auto_detect_user(users, portal_base)
        if auto_user:
            print(f"[*] 自动识别用户: {auto_user.get('name')} (Portal: {portal_base})")
            user = auto_user
        else:
            user = select_user(users)

    username = user["account"]
    plain_pwd = user["password"]
    service = user.get("server", "LT")
    print(f"\n[*] 已选择: {user.get('name', username)} ({username}) 服务: {service}")

    # 3. RSA 加密密码
    print("[*] 正在加密密码...")
    try:
        encrypted_pwd = encrypt_password(plain_pwd, mac, exponent, modulus)
        print(f"[+] 加密完成，密文长度: {len(encrypted_pwd)}")
    except Exception as e:
        print(f"❌ 密码加密失败: {e}")
        sys.exit(1)

    # 4. 发送登录请求
    print("[*] 执行登录...")
    try:
        result = do_login(portal_base, username, encrypted_pwd, service, query_string)
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        sys.exit(1)

    # 5. 处理认证结果
    if result.get("result") != "success":
        error_msg = result.get("message", "未知错误")
        print(f"❌ 认证失败: {error_msg}")
        sys.exit(1)

    print("✅ 认证成功！")
    user_index = result.get("userIndex")
    keepalive_interval = result.get("keepaliveInterval")
    print(f"   userIndex: {user_index}")
    print(f"   keepaliveInterval: {keepalive_interval} 秒")

    # 6. 保存 Portal 地址和用户信息到本地配置
    if not user_override:
        add_portal_to_user_weblist(username, portal_base)
        print(f"[*] 已保存 Portal 地址: {portal_base}")

        # 先保存 userIndex（login 响应直接提供，不依赖 getOnlineUserInfo）
        save_user_index(username, user_index)
        print(f"[*] 已保存 userIndex")

        # 再尝试获取更丰富的在线用户信息
        online_info = get_online_user_info(portal_base, user_index)
        if online_info:
            save_user_portal_info(username, online_info)
            print(f"[*] 已更新用户信息: {online_info.get('userName')}"
                  f" / {online_info.get('realServiceName')}"
                  f" / {online_info.get('userPackage')}")

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
