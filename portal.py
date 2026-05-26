#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Portal 探测与 API 交互模块。

负责捕获校园网强制门户重定向、调用 Portal API（pageInfo/login/logout/
getOnlineUserInfo）、检测当前网络状态。
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests

from config import load_users

# ---------- 常量 ----------
DETECT_URL = "http://www.baidu.com"          # 触发 Portal 重定向的外网地址
DEFAULT_MAC = "111111111"                     # 无法提取 MAC 时的默认值

# 使用 Session 保持 cookie，确保 login → getOnlineUserInfo 等跨请求的会话连续性
_session = requests.Session()


# ---------- 底层 API 请求 ----------
def _get_api(portal_base: str, method: str, params: Dict) -> Dict:
    """发送 GET 请求到 /eportal/InterFace.do，返回解析后的 JSON。"""
    url = urljoin(portal_base, f"/eportal/InterFace.do?method={method}")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = _session.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.json()


def _post_api(portal_base: str, method: str, data: Dict) -> Dict:
    """发送 POST 请求到 /eportal/InterFace.do，返回解析后的 JSON。"""
    url = urljoin(portal_base, f"/eportal/InterFace.do?method={method}")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = _session.post(url, data=data, headers=headers, timeout=10)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.json()


# ---------- Portal 重定向探测 ----------
def get_redirect_info(detect_url: str = DETECT_URL) -> str:
    """
    访问外网地址，获取 Portal 重定向的完整 URL（含 queryString）。
    返回如：http://172.16.54.18/eportal/index.jsp?wlanuserip=...
    """
    resp = requests.get(detect_url, timeout=10, allow_redirects=False)
    print(f"[DEBUG] get_redirect_info: {detect_url} → HTTP {resp.status_code}")
    if resp.status_code not in (301, 302, 303, 307, 308):
        raise Exception(f"未发生重定向 (HTTP {resp.status_code})，可能已在线或无需认证")
    location = resp.headers.get("Location")
    if not location:
        raise Exception("重定向响应中缺少 Location 头")
    print(f"[DEBUG]   Location: {location[:150]}...")
    return location


def extract_mac_from_query(query: str) -> str:
    """从 queryString 中提取 MAC 地址（wlanparameter 或 mac 参数）"""
    match = re.search(r"wlanparameter=([0-9A-Fa-f\-]+)", query)
    if not match:
        match = re.search(r"mac=([0-9A-Fa-f]+)", query)
    return match.group(1) if match else DEFAULT_MAC


# ---------- Portal API ----------
def fetch_page_info(portal_base: str, query_string: str) -> Dict:
    """调用 pageInfo API 获取 RSA 公钥、加密开关等配置（GET）。"""
    return _get_api(portal_base, "pageInfo", {"queryString": query_string})


def do_login(portal_base: str, username: str, encrypted_pwd: str,
             service: str, query_string: str) -> Dict:
    """执行登录请求（POST）"""
    data = {
        "userId": username,
        "password": encrypted_pwd,
        "service": service,
        "queryString": query_string,
        "operatorPwd": "",
        "operatorUserId": "",
        "validcode": "",
        "passwordEncrypt": "true",
        "method": "login",
    }
    return _post_api(portal_base, "login", data)


def do_logout(portal_base: str, user_index: str) -> Dict:
    """执行登出请求（POST）"""
    return _post_api(portal_base, "logout", {"userIndex": user_index})


def get_online_user_info(portal_base: str, user_index: str) -> Optional[Dict]:
    """获取当前在线用户的详细信息（POST），成功返回完整响应 dict。"""
    print(f"[DEBUG] getOnlineUserInfo: portal={portal_base}, userIndex={user_index[:40]}...")
    try:
        data = _post_api(portal_base, "getOnlineUserInfo", {"userIndex": user_index})
        result = data.get("result", "")
        msg = data.get("message", "")
        print(f"[DEBUG]   响应: result={result}, message={msg}")
        if result == "success":
            return data
        else:
            print(f"⚠️  获取在线信息失败: {msg}")
            return None
    except Exception as e:
        print(f"⚠️  获取在线信息异常: {e}")
        return None


def detect_portal() -> Tuple[str, str, str, str, str]:
    """
    探测 Portal 信息，合并重定向获取 + pageInfo + MAC 提取。
    返回 (portal_base, query_string, exponent, modulus, mac)
    """
    full_auth_url = get_redirect_info()
    parsed = urlparse(full_auth_url)
    portal_base = f"{parsed.scheme}://{parsed.netloc}"
    query_string = parsed.query
    info = fetch_page_info(portal_base, query_string)
    exponent = info.get("publicKeyExponent", "")
    modulus = info.get("publicKeyModulus", "")
    if not exponent or not modulus:
        raise Exception(f"pageInfo 返回缺少公钥字段: {json.dumps(info, ensure_ascii=False)[:200]}")
    mac = extract_mac_from_query(query_string)
    return portal_base, query_string, exponent, modulus, mac


# ---------- 已保存 Portal 地址的检测 ----------
def _collect_saved_portals() -> List[str]:
    """收集所有用户 webList 中出现过的 portal 地址（去重）。"""
    try:
        users = load_users()
    except Exception as e:
        print(f"[DEBUG] 加载用户配置失败: {e}")
        return []
    seen = set()
    result = []
    for u in users:
        for portal_base in u.get("webList", []):
            if portal_base not in seen:
                seen.add(portal_base)
                result.append(portal_base)
    print(f"[DEBUG] 已保存的 Portal 地址: {result if result else '(空)'}")
    return result


def _try_detect_online_user(portal_base: str) -> Optional[Dict]:
    """
    在给定 portal 上尝试用已保存的 userIndex 查询在线用户。
    返回 {"user": 用户配置, "info": 在线信息} 或 None。
    """
    # 先访问 Portal 首页获取 session cookie（JSESSIONID），后续 API 调用需要它
    print(f"[DEBUG] 预热 session: GET {portal_base}")
    try:
        warm_resp = _session.get(portal_base, timeout=5)
        print(f"[DEBUG] 预热响应: HTTP {warm_resp.status_code}, cookies: "
              f"{dict(_session.cookies.get_dict()) if _session.cookies else '(无)'}")
    except Exception as e:
        print(f"[DEBUG] 预热请求失败: {e}")

    try:
        users = load_users()
    except Exception as e:
        print(f"[DEBUG] 加载用户列表失败: {e}")
        return None

    print(f"[DEBUG] 共 {len(users)} 个用户，逐一尝试已保存的 userIndex...")
    for u in users:
        user_index = u.get("userIndex", "")
        account = u.get("account", "?")
        name = u.get("name", "?")
        if not user_index:
            print(f"[DEBUG]   跳过 {name}({account}): 无 userIndex")
            continue
        print(f"[DEBUG]   尝试 {name}({account}), userIndex={user_index[:30]}...")
        try:
            info = get_online_user_info(portal_base, user_index)
            if info and info.get("result") == "success":
                print(f"[DEBUG]   ✅ 匹配成功! userName={info.get('userName')}, "
                      f"service={info.get('realServiceName')}")
                return {"user": u, "info": info}
            else:
                msg = info.get("message", "无消息") if info else "返回 None"
                print(f"[DEBUG]   ❌ 失败: {msg}")
        except Exception as e:
            print(f"[DEBUG]   ❌ 异常: {e}")
    print(f"[DEBUG] 未匹配到任何在线用户")
    return None


# ---------- 网络状态检测 ----------
def _is_portal_redirect(location: str) -> bool:
    """判断重定向地址是否为校园网 Portal（而非普通的 HTTP→HTTPS 重定向）。"""
    return "/eportal/" in location


def _try_saved_portals():
    """
    尝试通过已保存的 portal 地址检测校园网环境和在线用户。
    返回 (status, portal_info, online_user) 或 None。
    """
    portals = _collect_saved_portals()
    if not portals:
        print("[DEBUG] _try_saved_portals: 没有已保存的 portal 地址")
        return None
    for portal_base in portals:
        print(f"[DEBUG] _try_saved_portals: 尝试直连 {portal_base}")
        try:
            resp = requests.get(portal_base, timeout=5)
            print(f"[DEBUG]   直连成功: HTTP {resp.status_code}")
        except Exception as e:
            print(f"[DEBUG]   直连失败: {e}")
            continue
        result = _try_detect_online_user(portal_base)
        if result:
            print(f"[DEBUG] _try_saved_portals: 识别到在线用户")
            return ("已连接校园网",
                    (portal_base, "", "", "", ""),
                    result)
        print(f"[DEBUG] _try_saved_portals: Portal 可达但未识别用户")
        return ("已连接校园网",
                (portal_base, "", "", "", ""),
                None)
    return None


def check_network_status():
    """
    检测当前网络状态。

    返回 (status_string, portal_info, online_user)

    status_string:
        "已连接校园网"           — 校园网已登录（自动识别在线用户）
        "已连接校园网，暂未登录"  — 检测到强制门户重定向
        "已连接网络(非校园网)"    — 互联网可达但非校园网
        "未连接任何网络"          — 无网络连接
    portal_info: (portal_base, query_string, exponent, modulus, mac) 或 None
    online_user: {"user": ..., "info": ...} 或 None
    """
    # 1. 尝试访问外网地址触发 Portal 重定向
    print(f"[DEBUG] check_network_status: 请求 {DETECT_URL}")
    try:
        resp = requests.get(DETECT_URL, timeout=10, allow_redirects=False)
        print(f"[DEBUG]   响应: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[DEBUG]   请求失败: {e}")
        # 网络不通，尝试直连已保存的 portal 地址
        saved = _try_saved_portals()
        result = saved if saved else ("未连接任何网络", None, None)
        print(f"[DEBUG] 最终状态: {result[0]}")
        return result

    location = resp.headers.get("Location", "")
    if location:
        print(f"[DEBUG]   Location: {location[:120]}...")

    # 2. 强制门户重定向（Location 包含 /eportal/）→ 校园网，未登录
    if resp.status_code in (301, 302, 303, 307, 308) and _is_portal_redirect(location):
        print("[DEBUG]   识别为 Portal 重定向 → 未登录")
        try:
            parsed = urlparse(location)
            portal_base = f"{parsed.scheme}://{parsed.netloc}"
            query_string = parsed.query
            info = fetch_page_info(portal_base, query_string)
            exponent = info.get("publicKeyExponent", "")
            modulus = info.get("publicKeyModulus", "")
            if not exponent or not modulus:
                raise Exception("公钥字段缺失")
            mac = extract_mac_from_query(query_string)
            result = ("已连接校园网，暂未登录",
                      (portal_base, query_string, exponent, modulus, mac),
                      None)
            print(f"[DEBUG] 最终状态: {result[0]}")
            return result
        except Exception as e:
            print(f"[DEBUG]   Portal 解析失败: {e}")
            result = ("已连接校园网，暂未登录", None, None)
            print(f"[DEBUG] 最终状态: {result[0]}")
            return result

    if resp.status_code in (301, 302, 303, 307, 308):
        print("[DEBUG]   3xx 但不是 Portal 重定向 (如 HTTP→HTTPS) → 视为互联网可达")

    # 3. 互联网可达（200 或非 Portal 的 3xx）→ 尝试已保存 portal 地址
    if resp.status_code == 200 or resp.status_code in (301, 302, 303, 307, 308):
        print("[DEBUG]   互联网可达，尝试已保存 portal...")
        saved = _try_saved_portals()
        if saved:
            print(f"[DEBUG] 最终状态: {saved[0]}")
            return saved
        result = ("已连接网络(非校园网)", None, None)
        print(f"[DEBUG] 最终状态: {result[0]}")
        return result

    # 4. 其他状态码
    print(f"[DEBUG]   非预期状态码 {resp.status_code}，尝试已保存 portal...")
    saved = _try_saved_portals()
    result = saved if saved else ("未连接任何网络", None, None)
    print(f"[DEBUG] 最终状态: {result[0]}")
    return result
