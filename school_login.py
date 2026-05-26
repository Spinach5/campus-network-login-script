#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import execjs
import sys
import json
import re
import requests
from urllib.parse import urlparse, urljoin

DETECT_URL = "http://www.baidu.com"
DEFAULT_MAC = "111111111"


def get_redirect_info(detect_url=DETECT_URL):
    resp = requests.get(detect_url, timeout=10, allow_redirects=False)
    if resp.status_code not in (301, 302, 303, 307, 308):
        raise Exception(f"未发生重定向 (状态码 {resp.status_code})，可能已在线")
    location = resp.headers.get("Location")
    if not location:
        raise Exception("重定向响应中无 Location 头")
    return location


def _post_api(portal_base, method, data):
    """POST 到 /eportal/InterFace.do?method=xxx，返回解析后的 JSON。"""
    url = urljoin(portal_base, f"/eportal/InterFace.do?method={method}")
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    resp = requests.post(url, data=data, headers=headers, timeout=10)
    return resp.json()


def fetch_page_info(portal_base, query_string):
    """调用 pageInfo API 获取加密公钥及其他配置。"""
    data = {"queryString": query_string}
    return _post_api(portal_base, "pageInfo", data)


def load_users(json_path="py/password.json"):
    if not os.path.exists(json_path):
        json_path = "password.json"
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"未找到配置文件: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        users = json.load(f)
    if not isinstance(users, list):
        raise ValueError("password.json 格式错误")
    return users


def select_user(users):
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


def encrypt_password(plain_pwd, exponent, modulus):
    """使用与 portal 页面完全一致的逻辑加密密码。"""
    js_path = os.path.join(os.path.dirname(__file__), "rsa_full.js")
    if not os.path.exists(js_path):
        raise FileNotFoundError("缺失 rsa_full.js 文件")
    with open(js_path, "r", encoding="utf-8") as f:
        rsa_lib = f.read()
    # rsa_full.js 原先面向浏览器（})(window)），execjs 底层是 Node.js 需要 globalThis
    rsa_lib = rsa_lib.replace("})(window)", "})(globalThis)")
    js_code = rsa_lib + f"""
    function doEncrypt() {{
        var passwordEncode = "{plain_pwd}".split("").reverse().join("");
        RSAUtils.setMaxDigits(400);
        var key = new RSAUtils.getKeyPair("{exponent}", "", "{modulus}");
        return RSAUtils.encryptedString(key, passwordEncode);
    }}
    """
    ctx = execjs.compile(js_code)
    encrypted = ctx.call("doEncrypt")
    return encrypted.replace(" ", "")


def do_login(portal_base, username, encrypted_pwd, service, query_string):
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


def get_online_user_info(portal_base, user_index):
    url = urljoin(portal_base, "/eportal/InterFace.do?method=getOnlineUserInfo")
    params = {"method": "getOnlineUserInfo", "userIndex": user_index}
    resp = requests.get(url, params=params, timeout=10)
    try:
        data = resp.json()
        if data.get("result") == "success":
            return data.get("userUrl")
        else:
            print(f"⚠️ 获取在线信息失败: {data.get('message')}")
            return None
    except Exception:
        print("⚠️ 解析在线信息失败")
        return None


def extract_mac_from_query(query):
    match = re.search(r"wlanparameter=([0-9A-Fa-f\-]+)", query)
    if not match:
        match = re.search(r"mac=([0-9A-Fa-f]+)", query)
    if match:
        return match.group(1)
    return DEFAULT_MAC


def main():
    # 1. 探测认证地址
    print("[*] 正在探测 Portal 认证地址...")
    try:
        full_auth_url = get_redirect_info()
        print(f"[*] 完整认证页面: {full_auth_url}")
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    parsed = urlparse(full_auth_url)
    portal_base = f"{parsed.scheme}://{parsed.netloc}"
    query_string = parsed.query
    print(f"[*] Portal 基础地址: {portal_base}")

    # 2. 通过 pageInfo API 获取 RSA 公钥
    print("[*] 调用 pageInfo API 获取加密密钥...")
    try:
        info = fetch_page_info(portal_base, query_string)
        exponent = info.get("publicKeyExponent", "")
        modulus = info.get("publicKeyModulus", "")
        if not exponent or not modulus:
            raise Exception(f"pageInfo 返回中缺少公钥: {json.dumps(info, ensure_ascii=False)[:300]}")
        print(f"[+] 公钥获取成功")
        print(f"    exponent: {exponent}")
        print(f"    modulus: {modulus[:40]}...")
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    # 3. 选择用户
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
    print(f"\n[*] 已选择: {user.get('name')} ({username}) 服务: {service}")

    mac = extract_mac_from_query(query_string)
    print(f"[*] 使用 MAC: {mac}")

    # 4. 加密密码
    print("[*] 正在加密密码...")
    try:
        encrypted_pwd = encrypt_password(plain_pwd, exponent, modulus)
        print(f"[+] 加密完成，密文长度: {len(encrypted_pwd)}")
    except Exception as e:
        print(f"❌ 密码加密失败: {e}")
        sys.exit(1)

    # 5. 执行登录
    print("[*] 执行登录...")
    try:
        result = do_login(portal_base, username, encrypted_pwd, service, query_string)
    except Exception as e:
        print(f"❌ 登录请求失败: {e}")
        sys.exit(1)

    if result.get("result") != "success":
        error_msg = result.get("message", "未知错误")
        print(f"❌ 认证失败: {error_msg}")
        sys.exit(1)

    print("✅ 认证成功！")
    user_index = result.get("userIndex")
    keepalive_interval = result.get("keepaliveInterval")
    print(f"   userIndex: {user_index}")
    print(f"   keepaliveInterval: {keepalive_interval} 秒")

    if user_index:
        print("[*] 正在获取上网重定向地址...")
        user_url = get_online_user_info(portal_base, user_index)
        if user_url:
            print(f"\n📡 重定向地址: {user_url}")
        else:
            print("\n⚠️ 未能获取 userUrl，但认证已通过")
    else:
        print("\n⚠️ 未返回 userIndex，但认证已通过")


if __name__ == "__main__":
    main()
