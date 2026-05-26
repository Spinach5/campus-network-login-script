# 校园网登录脚本

## 需要安装的包

```
import os
import sys
import execjs
import json
import re
import requests
from urllib.parse import urlparse, urljoin
```

## rsa_full.js

这是rsa加密的js文件,从原本的网页获取

## 密码文件

1. 将password.example.json重命名为password.json

2. 修改py目录下的password.json文件


3. 密码文件格式为：名称,学号,密码,运营商
[{"name": "名称","account": "学号", "password": "密码", "server": "运营商代码"}]

4. 运营商代码：LT 联通 YD 移动 DX 电信

`脚本会自动从password.json文件中读取用户信息，并自动选择运营商`

## 运行脚本

```py
python3 school_login.py
```

根据提示选择用户