#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动登录脚本
支持多账号、自动探测 Portal、RSA 密码加密、运营商选择。
"""

import os
import sys
import json
import re
import argparse
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Tuple

import requests
import execjs


# ---------- 常量配置 ----------
DETECT_URL = "http://www.baidu.com"   # 用于触发 Portal 重定向的外网地址
DEFAULT_MAC = "111111111"              # 当无法从 queryString 提取 MAC 时的默认值
RSA_JS_FILE = "rsa_full.js"            # 前端 RSA 加密库文件


# ---------- 工具函数 ----------
def get_redirect_info(detect_url: str = DETECT_URL) -> str:
    """
    访问外网地址，获取 Portal 重定向的完整 URL（含 queryString）。
    返回如：http://172.16.54.18/eportal/index.jsp?wlanuserip=...
    """
    resp = requests.get(detect_url, timeout=10, allow_redirects=False)
    if resp.status_code not in (301, 302, 303, 307, 308):
        raise Exception(f"未发生重定向 (HTTP {resp.status_code})，可能已在线或无需认证")
    location = resp.headers.get("Location")
    if not location:
        raise Exception("重定向响应中缺少 Location 头")
    return location


def _get_api(portal_base: str, method: str, params: Dict) -> Dict:
    """
    发送 GET 请求到 /eportal/InterFace.do，返回解析后的 JSON。
    适用于 pageInfo、getOnlineUserInfo 等接口。
    """
    url = urljoin(portal_base, f"/eportal/InterFace.do?method={method}")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.get(url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post_api(portal_base: str, method: str, data: Dict) -> Dict:
    """
    发送 POST 请求到 /eportal/InterFace.do，返回解析后的 JSON。
    适用于 login 等接口。
    """
    url = urljoin(portal_base, f"/eportal/InterFace.do?method={method}")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(url, data=data, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_page_info(portal_base: str, query_string: str) -> Dict:
    """
    调用 pageInfo API 获取 RSA 公钥、加密开关等配置。
    注意：此接口为 GET 请求，参数 queryString 通过 URL 传递。
    """
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
    data = {"userIndex": user_index}
    return _post_api(portal_base, "logout", data)


def get_online_user_info(portal_base: str, user_index: str) -> Optional[str]:
    """获取用户的上网重定向地址（userUrl）"""
    try:
        data = _get_api(portal_base, "getOnlineUserInfo", {"userIndex": user_index})
        if data.get("result") == "success":
            return data.get("userUrl")
        else:
            print(f"⚠️ 获取在线信息失败: {data.get('message')}")
            return None
    except Exception as e:
        print(f"⚠️ 获取在线信息异常: {e}")
        return None


def extract_mac_from_query(query: str) -> str:
    """从 queryString 中提取 MAC 地址（wlanparameter 或 mac 参数）"""
    match = re.search(r"wlanparameter=([0-9A-Fa-f\-]+)", query)
    if not match:
        match = re.search(r"mac=([0-9A-Fa-f]+)", query)
    return match.group(1) if match else DEFAULT_MAC


def detect_portal() -> Tuple[str, str, str, str, str]:
    """
    探测 Portal 信息，合并 get_redirect_info + fetch_pageInfo + MAC 提取。
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


NETWORK_CHECK_URL = "http://www.msftconnecttest.com/connecttest.txt"


def check_network_status() -> Tuple[str, Optional[Tuple[str, str, str, str, str]]]:
    """
    检测当前网络状态。

    返回 (status_string, portal_info_or_None)

    status_string:
        "已连接校园网"           — 互联网可达且处于校园网内
        "已连接校园网，暂未登录"  — 检测到强制门户重定向
        "已连接网络(非校园网)"    — 互联网可达但非校园网
        "未连接任何网络"          — 无网络连接
    portal_info: (portal_base, query_string, exponent, modulus, mac) 或 None
    """
    # 1. 尝试访问公网测试地址
    try:
        resp = requests.get(NETWORK_CHECK_URL, timeout=10, allow_redirects=False)
    except Exception:
        return "未连接任何网络", None

    # 2. 根据响应状态码判断
    if resp.status_code == 200:
        # 互联网可达，进一步检查是否在校园网内
        try:
            portal_info = detect_portal()
            return "已连接校园网", portal_info
        except Exception:
            return "已连接网络(非校园网)", None

    if resp.status_code in (301, 302, 303, 307, 308):
        # 被重定向到强制门户 → 校园网，未登录
        location = resp.headers.get("Location", "")
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
            return "已连接校园网，暂未登录", (portal_base, query_string, exponent, modulus, mac)
        except Exception:
            return "已连接校园网，暂未登录", None

    # 其他状态码（404、500 等）
    return "未连接任何网络", None


# ---------- 用户配置处理 ----------
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
        print("没有账号信息")
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


# ---------- RSA 加密 ----------
def encrypt_password(plain_pwd: str, mac: str, exponent: str, modulus: str) -> str:
    """
    使用与 Portal 前端完全一致的逻辑加密密码：
    1. 拼接 "密码>MAC"
    2. 反转整个字符串
    3. 调用 RSAUtils.encryptedString 加密
    """
    js_path = os.path.join(os.path.dirname(__file__), RSA_JS_FILE)
    if not os.path.exists(js_path):
        raise FileNotFoundError(f"缺失 {RSA_JS_FILE} 文件，请确保该文件存在")

    with open(js_path, "r", encoding="utf-8") as f:
        rsa_lib = f.read()

    # 适配 Node.js 环境（原库依赖浏览器 window 对象）
    rsa_lib = rsa_lib.replace("})(window)", "})(globalThis)")

    # 构造待加密字符串并反转
    combined = f"{plain_pwd}>{mac}"
    reversed_str = combined[::-1]

    js_code = rsa_lib + f"""
    function doEncrypt() {{
        var passwordEncode = "{reversed_str}";
        RSAUtils.setMaxDigits(400);
        var key = new RSAUtils.getKeyPair("{exponent}", "", "{modulus}");
        var encrypted = RSAUtils.encryptedString(key, passwordEncode);
        return encrypted.replace(/ /g, "");
    }}
    """
    ctx = execjs.compile(js_code)
    encrypted = ctx.call("doEncrypt")
    return encrypted


# ---------- 主流程 ----------
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