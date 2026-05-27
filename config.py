#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户配置管理模块。

管理 py/password.json 的读写、账号选择、Portal 地址关联。
"""

import os
import json
from typing import Dict, List, Optional

from log_utils import get_logger

logger = get_logger(__name__)

PASSWORD_FILE = "py/password.json"


def init_password_file(json_path: str = PASSWORD_FILE) -> bool:
    """确保 password.json 存在，若不存在则创建空数组。返回 True 表示新创建。"""
    if not os.path.exists(json_path):
        os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            f.write("[]")
        return True
    return False


def load_users(json_path: str = PASSWORD_FILE) -> List[Dict]:
    """加载用户配置文件，若文件不存在则自动初始化。为空时打印提示。"""
    init_password_file(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        users = json.load(f)
    if not isinstance(users, list):
        raise ValueError("password.json 格式错误，应为 JSON 数组")
    if not users:
        logger.warning("没有账号信息")
    else:
        logger.debug("加载了 %d 个用户", len(users))
    return users


def save_users(users: List[Dict], json_path: str = PASSWORD_FILE) -> None:
    """保存用户列表到配置文件"""
    os.makedirs(os.path.dirname(json_path) or ".", exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def select_user(users: List[Dict]) -> Dict:
    """交互式选择要登录的账号"""
    print("\n========== 请选择登录账号 ==========")
    for idx, u in enumerate(users, 1):
        name = u.get("name", "未命名")
        account = u.get("account", "")
        server = u.get("server", "LT")
        print(f"{idx}. {name} (账号: {account}, 服务: {server})")
    while True:
        try:
            choice = int(input("请输入序号: "))
            if 1 <= choice <= len(users):
                return users[choice - 1]
            print(f"请输入 1 ~ {len(users)} 之间的数字")
        except ValueError:
            print("输入无效，请输入数字")


def auto_detect_user(users: List[Dict], portal_base: str) -> Optional[Dict]:
    """根据 portal_base 在用户 webList 中匹配，唯一匹配时返回该用户，否则返回 None。"""
    matches = [u for u in users if portal_base in u.get("webList", [])]
    return matches[0] if len(matches) == 1 else None


def add_portal_to_user_weblist(account: str, portal_base: str,
                                json_path: str = PASSWORD_FILE) -> None:
    """将 portal_base 添加到指定用户的 webList（去重），保存到文件。"""
    users = load_users(json_path)
    for u in users:
        if u.get("account") == account:
            u.setdefault("webList", [])
            if portal_base not in u["webList"]:
                u["webList"].append(portal_base)
                save_users(users, json_path)
                logger.info("已保存 Portal 地址到 %s: %s", account, portal_base)
            return


def save_user_index(account: str, user_index: str,
                     json_path: str = PASSWORD_FILE) -> None:
    """将登录返回的 userIndex 立即保存到本地配置（登录成功后总是调用）。"""
    users = load_users(json_path)
    for u in users:
        if u.get("account") == account:
            u["userIndex"] = user_index
            save_users(users, json_path)
            logger.info("已保存 userIndex: %s", account)
            return


def save_user_portal_info(account: str, info: Dict,
                           json_path: str = PASSWORD_FILE) -> None:
    """将 Portal 返回的在线用户信息合并到本地配置中。"""
    users = load_users(json_path)
    for u in users:
        if u.get("account") == account:
            u["userName"] = info.get("userName", u.get("userName", ""))
            u["userId"] = info.get("userId", u.get("userId", ""))
            u["userMac"] = info.get("userMac", u.get("userMac", ""))
            u["realServiceName"] = info.get("realServiceName", u.get("realServiceName", ""))
            u["userPackage"] = info.get("userPackage", u.get("userPackage", ""))
            u["userIndex"] = info.get("userIndex", u.get("userIndex", ""))
            save_users(users, json_path)
            logger.info("已更新用户信息: %s / %s / %s",
                        info.get("userName"), info.get("realServiceName"),
                        info.get("userPackage"))
            return
