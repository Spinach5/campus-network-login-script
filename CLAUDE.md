# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

校园网 (campus network) captive portal auto-login script for 深澜 (Srun) portal systems. Detects the portal redirect, fetches RSA public key parameters via the portal API, encrypts the password with pure Python RSA, and submits the authentication request.

## Commands

```bash
pip install -r requirements.txt   # install dependencies (requests)
python3 school_login.py           # run the script
```

Requires Python 3.7+ only. RSA encryption is pure Python — no Node.js needed.

## Architecture

```
school_login.py          # CLI entry point — orchestrates login flow
portal.py                # Portal detection, API calls, network status
crypto.py                # Pure Python RSA encryption (pow-based, no execjs)
config.py                # User config CRUD (password.json), auto-detect, portal info persistence
gui.py                   # Tkinter GUI
log_utils.py             # Logging setup (date-based dirs, password masking)
rsa_full.js              # Reference: original JS RSA library (no longer used at runtime)
py/password.json         # User credentials (gitignored, use py/password.example.json as template)
requirements.txt         # pip dependencies
```

### Module responsibilities

**`portal.py`** — All network/Portal interaction:
- `get_redirect_info()` — GETs `http://www.baidu.com` to trigger captive portal redirect
- `detect_portal()` — combines redirect + `pageInfo` + MAC extraction into one call
- `fetch_page_info()` — GET `/eportal/InterFace.do?method=pageInfo` for RSA public key
- `do_login()` / `do_logout()` — POST login/logout requests
- `get_online_user_info()` — POST, returns full user detail dict (userName, service, package, etc.)
- `check_network_status()` — full network detection: redirect detection, saved-portal fallback, online user identification
- `_get_api()` / `_post_api()` — generic Portal API helpers (hit `/eportal/InterFace.do?method=...`)

**`crypto.py`** — RSA password encryption:
- `encrypt_password()` — pure Python RSA: `{password}>{MAC}` + reverse + RSA via `pow(x, e, m)`
- `_bi_to_hex()` — matches JS `biToHex` output format (16-bit digits, 4 hex chars each, zero-padded)

**`config.py`** — Local user configuration:
- `load_users()` / `save_users()` — read/write `py/password.json`
- `select_user()` — interactive CLI account picker
- `auto_detect_user()` — match current portal_base against users' `webList`
- `add_portal_to_user_weblist()` — save portal address to user config
- `save_user_portal_info()` — persist online user details (userName, userId, userMac, etc.) from `getOnlineUserInfo`

**`school_login.py`** — CLI entry point, imports from the three modules above and runs the login flow.

**`gui.py`** — Tkinter GUI, imports from `portal`, `crypto`, `config`.

**Login flow in `school_login.py`:**

1. `detect_portal()` — triggers redirect → parses portal_base + query_string + RSA keys + MAC
2. `load_users()` / `auto_detect_user()` / `select_user()` — load config, auto-match or prompt
3. `encrypt_password()` — RSA-encrypt with Portal public key
4. `do_login()` — POST credentials
5. On success: `add_portal_to_user_weblist()` + `get_online_user_info()` + `save_user_portal_info()`

## RSA encryption

The encryption scheme is specific to 深澜 portals, implemented in pure Python in `crypto.py`:

1. Concatenate: `{password}>{MAC}`
2. Reverse the entire string
3. Convert to char codes, zero-pad to chunkSize (matching JS `encryptedString`)
4. Parse exponent/modulus hex strings to Python `int`
5. For each chunk: pack bytes as `int` (little-endian, matching JS BigInt construction), then `pow(block, e, m)`
6. Convert result to hex via `_bi_to_hex()` — matches JS `biToHex` (16-bit digits, 4 hex chars each, high-first)
7. Join all chunk hex outputs (no spaces)

`rsa_full.js` is kept as reference only — it is the original JS extracted from the portal page. If the portal updates its encryption, compare against this file to update `crypto.py`.

## Logging

Logs are written to `py/{YYYY-MM-DD}-logs/login-{HH-MM-SS}-{microseconds}.log`. The `log_utils` module provides:
- `get_logger(name)` — returns a configured logger (file: DEBUG, console: INFO)
- `mask_password(pwd)` — returns `pwd[:2] + "****"` for safe logging

## Password config format

`py/password.json` is a JSON array (template at `py/password.example.json`):

```json
[{
  "name": "Display Name",
  "account": "student_id",
  "password": "plaintext_pwd",
  "server": "LT",
  "webList": [],
  "userName": "",
  "userId": "",
  "userMac": "",
  "realServiceName": "",
  "userPackage": "",
  "userIndex": ""
}]
```

- `server`: ISP code — `LT` (联通), `YD` (移动), `DX` (电信)
- `webList`: auto-populated portal addresses the user has connected from
- `userName`/`userId`/etc.: auto-populated from `getOnlineUserInfo` after first successful login

## Notes

- `DETECT_URL` is `http://www.baidu.com` (not HTTPS) — captive portals intercept HTTP but pass HTTPS through.
- The `pageInfo` API is a GET request; `login`, `logout`, `getOnlineUserInfo` are POST.
- `check_network_status()` returns a 3-tuple `(status, portal_info, online_user)` — the third element carries auto-detected user info when the user is already logged in.
- `rsa_full.js` is kept as a reference file; RSA encryption is now pure Python in `crypto.py`.
- Logs are saved to `py/{date}-logs/` directory; the pattern is gitignored.
