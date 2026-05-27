#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RSA 密码加密模块。

纯 Python 实现，与 Portal 前端的 RSAUtils.encryptedString 逻辑完全一致，
无需 Node.js / execjs。
"""

from log_utils import get_logger, mask_password

logger = get_logger(__name__)


def _bi_to_hex(x: int) -> str:
    """
    将整数转换为十六进制字符串，匹配 JS RSAUtils.biToHex 的输出格式。

    JS 的 biToHex 从 biHighIndex(x) 向下迭代到 0，每个 digit（16-bit）
    输出恰好 4 个十六进制字符（含前导零）。
    """
    if x == 0:
        return "0000"
    num_digits = max(1, (x.bit_length() + 15) // 16)
    parts = []
    for i in range(num_digits - 1, -1, -1):
        digit = (x >> (i * 16)) & 0xFFFF
        parts.append(f"{digit:04x}")
    return "".join(parts)


def encrypt_password(plain_pwd: str, mac: str, exponent: str, modulus: str) -> str:
    """
    加密密码，与 Portal 前端 RSAUtils.encryptedString 逻辑一致。

    流程：
    1. 拼接 "{密码}>{MAC}" 并反转字符串
    2. 将字符串转换为字符码数组（匹配 JS charCodeAt）
    3. 零填充到 chunkSize 的倍数
    4. 逐块 RSA 加密（与 JS 等价的字节打包 + 模幂运算）
    5. 拼接所有块的十六进制输出，去除空格
    """
    # 1. 构造待加密字符串并反转
    combined = f"{plain_pwd}>{mac}"
    reversed_str = combined[::-1]

    # 2. 转换为字符码（匹配 JS charCodeAt，对 ASCII 等同于 ord）
    data = [ord(c) for c in reversed_str]

    # 3. 解析 RSA 公钥参数
    e_int = int(exponent, 16)
    m_int = int(modulus, 16)

    # 4. 计算 chunkSize（匹配 JS: 2 * biHighIndex(modulus)）
    #    biHighIndex = ceil(bit_length / 16) - 1，即最高非零 digit 的索引
    bi_high_index = max(0, (m_int.bit_length() + 15) // 16 - 1)
    chunk_size = 2 * bi_high_index
    if chunk_size < 2:
        chunk_size = 2

    # 5. 零填充到 chunk_size 边界（匹配 JS 的零字节填充）
    data_len = len(data)
    if data_len % chunk_size != 0:
        pad_len = chunk_size - (data_len % chunk_size)
        data.extend([0] * pad_len)

    logger.info(
        "加密密码: plain_len=%d, mac=%s, chunk_size=%d, chunk_count=%d",
        len(plain_pwd), mac, chunk_size, len(data) // chunk_size,
    )

    # 6. 逐块加密
    hex_parts = []
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        # 打包字节为大整数 — 匹配 JS encryptedString 中每 2 字节组成一个
        # BigInt digit 的逻辑：digits[j] = a[k] + (a[k+1] << 8)
        # 这在 Python 中等价于小端序字节解释
        block_int = 0
        j = 0
        for k in range(0, len(chunk), 2):
            lo = chunk[k]
            hi = chunk[k + 1]
            block_int |= (lo | (hi << 8)) << (j * 16)
            j += 1

        crypt_int = pow(block_int, e_int, m_int)
        hex_parts.append(_bi_to_hex(crypt_int))

    # 7. 拼接并去除所有空格（匹配 JS encryptedString 的 replace(/ /g, "")）
    result = "".join(hex_parts)
    logger.info("加密完成: encrypted_len=%d", len(result))
    return result
