<p align="center">
<img src="https://foruda.gitee.com/avatar/1777480666913616794/16193480_damn_2_1777480666.png" width="100">
</p>

# 校园网自动登录脚本
一个轻量、易用的校园网自动登录工具，支持多账号配置、自动加密认证，一键完成校园网登录认证，告别手动登录网页的繁琐操作。

## ✨ 特性
- 支持多账号配置，自由切换登录用户
- 自动完成密码 RSA 加密，适配校园网认证规则
- 支持联通/移动/电信三大运营商选择
- 依赖极简，配置简单，一键运行

## 📋 运行环境
- [Python 3.x](https://www.python.org/)
- [Node.js](https://nodejs.org/zh-cn)（用于执行 RSA 加密脚本）

## 📦 安装依赖
### 1. 安装 Python 依赖包
项目根目录下执行命令：
```bash
pip install -r requirements.txt
```

### 2. 核心依赖说明
脚本依赖以下 Python 库：
```python
import os
import sys
import execjs
import json
import re
import requests
from urllib.parse import urlparse, urljoin
```

## 📝 配置账号信息
### 1. 重命名配置文件
将项目中的 `password.example.json` 重命名为 `password.json`

### 2. 填写账号密码
编辑 `password.json` 文件，按照格式填写你的信息：
```json
[
    {
        "name": "自定义名称",
        "account": "学号",
        "password": "密码",
        "server": "运营商代码"
    }
]
```

### 3. 运营商代码对照表
| 运营商 | 代码 |
|--------|------|
| 联通   | LT   |
| 移动   | YD   |
| 电信   | DX   |

> 脚本会自动读取配置文件中的账号信息，并自动匹配对应运营商

## 📂 文件说明
- `school_login.py`：主登录脚本，执行登录逻辑
- `password.json`：账号密码配置文件（需自行创建）
- `rsa_full.js`：校园网官方 RSA 加密脚本，依赖 Node.js 运行

## 🚀 运行脚本
在项目根目录执行启动命令：
```bash
python3 school_login.py
```
根据终端提示，选择需要登录的账号即可完成自动登录。

## ⚠️ 注意事项
1. 确保已正确安装 Python 和 Node.js 环境
2. 首次使用务必配置好 `password.json` 文件
3. 密码仅用于本地加密认证，不会上传任何第三方服务器
