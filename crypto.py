#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSA 密码加密模块。

使用 execjs 调用前端 rsa_full.js，实现与 Portal 一致的密码加密逻辑。
"""

import os
import execjs

RSA_JS_FILE = "rsa_full.js"


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
