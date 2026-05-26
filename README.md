<p align="center">
<img src="https://foruda.gitee.com/avatar/1777480666913616794/16193480_damn_2_1777480666.png" width="100">
</p>

# 校园网自动登录脚本

一个轻量、易用的校园网自动登录工具，支持多账号配置、自动 RSA 加密认证、运营商选择，一键完成校园网登录认证，彻底告别手动打开网页输密码的繁琐操作。

## ✨ 特性

- **多账号支持**：可配置多个账号，运行时自由选择切换
- **自动加密**：模拟前端 RSA 加密流程，适配校园网 Portal 认证规则
- **运营商兼容**：支持联通（LT）、移动（YD）、电信（DX）三大运营商
- **极简依赖**：仅需 Python 3 和 Node.js，无额外复杂环境
- **一键运行**：交互式选择账号，自动完成认证并输出上网重定向地址

## 📋 运行环境

| 环境          | 版本要求             | 备注                                 |
| ------------- | -------------------- | ------------------------------------ |
| Python        | 3.7 及以上           | 开发测试环境为 Python 3.10+          |
| Node.js       | 12.x 及以上          | 用于执行 `execjs` 调用 RSA 加密脚本  |
| pip           | 对应 Python 版本     | 用于安装依赖                         |

> 建议使用虚拟环境（`venv`）隔离项目依赖，避免污染系统 Python 环境。

## 📦 项目依赖（Python 库）

脚本依赖以下 Python 第三方库（已列在 `requirements.txt` 中）：

```text
requests>=2.34.2
execjs>=1.5.1
```

标准库中使用的模块（无需额外安装）：
- `os`, `sys`, `json`, `re`, `gzip`, `urllib.parse`

## 📝 配置账号信息

### 1. 创建配置文件

将项目中的 `password.example.json` 重命名为 `password.json`（若不存在示例文件，则直接新建该文件）。

### 2. 编辑配置文件

按以下 JSON 格式填写你的校园网账号信息：

```json
[
    {
        "name": "自定义名称（如：张三）",
        "account": "学号/工号",
        "password": "明文密码",
        "server": "运营商代码（LT / YD / DX）"
    },
    {
        "name": "李四",
        "account": "20240001",
        "password": "mypassword",
        "server": "YD"
    }
]
```

### 3. 运营商代码对照表

| 运营商   | 代码   |
|----------|--------|
| 中国联通 | `LT`   |
| 中国移动 | `YD`   |
| 中国电信 | `DX`   |

> 脚本会自动根据 `server` 字段匹配运营商，无需手动修改其他配置。

## 📂 项目文件说明

| 文件名               | 作用                                                           |
| -------------------- | -------------------------------------------------------------- |
| `school_login.py`    | 主登录脚本，包含自动探测 Portal、获取公钥、加密密码、发送认证请求等核心逻辑 |
| `password.json`      | 用户账号配置文件（**需用户自行创建**，不提交至版本控制）       |
| `rsa_full.js`        | 从校园网 Portal 页面提取的原始 RSA 加密脚本（**静态文件**，无需修改） |
| `requirements.txt`   | Python 依赖清单，用于 `pip install -r requirements.txt`        |

## 🚀 各平台运行方式

> **前提**：已安装 Python 3 和 Node.js，并确保 `node` 命令可在终端中执行。

所有步骤均在**项目根目录**下执行。

### 1. Linux / macOS

```bash
# （推荐）创建并激活虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装 Python 依赖
pip install -r requirements.txt

# 运行脚本
python3 school_login.py
```

### 2. Windows（PowerShell 或 CMD）

```bash
# （推荐）创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行脚本
python school_login.py
```

## 运行参数
```bash
#使用gui界面
python school_login.py

#使用命令行选择
python school_login.py -cli

#使用命令行指定账号,密码,运营商
python school_login.py -u <account> -p <password> -s <server>

```


## ⚠️ 注意事项

1. **环境要求**  
   - 必须安装 Node.js，且确保 `node --version` 能正常输出版本号。  
   - 如果不需要 `execjs`（即不想依赖 Node.js），可使用“纯 Python RSA 加密”替代方案（需自行修改脚本）。

2. **配置文件安全**  
   - `password.json` 包含明文密码，请妥善保管，**切勿提交至公开代码仓库**。建议将 `password.json` 加入 `.gitignore`。

3. **网络要求**  
   - 脚本依赖访问 `http://www.baidu.com` 触发 Portal 重定向，请确保未登录状态下能正常被重定向到认证页面。

4. **运营商代码**  
   - 请根据实际购买的宽带服务正确填写 `server` 字段，否则可能导致认证失败。

5. **加密脚本来源**  
   - `rsa_full.js` 是从校园网 Portal 登录页面提取的原始加密库，未做任何修改。若 Portal 更新加密方式，需同步更新该文件。

## ❓ 常见问题

### Q1: 运行时报错 `ModuleNotFoundError: No module named 'execjs'`

A: 未安装依赖，请执行 `pip install -r requirements.txt`（确保已激活虚拟环境）。

### Q2: 提示 `缺失 rsa_full.js 文件`

A: 请确认 `rsa_full.js` 文件存在于脚本同目录下，且内容完整（可从 Portal 页面源码中提取或从项目 release 中获取）。

### Q3: 认证失败，返回 `passwordEncrypt` 错误或 `message` 包含“加密错误”

A: 可能原因：
- 公钥参数未正确获取（检查网络是否能正常访问 Portal 页面）
- MAC 地址提取错误（可手动设置 `DEFAULT_MAC` 常量测试）
- 密码中包含了特殊字符（如中文），前端加密仅取低 8 位，可尝试将密码设为纯 ASCII 字符

### Q4: Linux 下使用 `pip install` 报错 `externally-managed-environment`

A: 这是系统 Python 环境受保护所致，请使用虚拟环境（`venv`）或在命令后添加 `--break-system-packages`（不推荐）。

### Q5: 如何在不安装 Node.js 的情况下使用？

A：可以采用“纯 Python RSA 加密”实现（将 `encrypt_password` 函数替换为基于 `pow` 的实现），但需确保与前端加密逻辑完全一致。可参考项目 issues 中的相关讨论。

## 📄 许可证

本项目仅供学习交流使用，请勿用于任何商业或非法用途。使用本工具造成的任何后果由使用者自行承担。

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request 改进脚本。如有校园网 Portal 接口变动导致的失效问题，请提供相关页面源码以便适配。