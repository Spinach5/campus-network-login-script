# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

校园网 (campus network) captive portal auto-login script for 深澜 (Srun) portal systems. Detects the portal redirect, fetches RSA public key parameters via the portal API, encrypts the password in-browser-style via `execjs`, and submits the authentication request.

## Commands

```bash
pip install -r requirements.txt   # install dependencies (pyexecjs, requests)
python3 school_login.py           # run the script
```

Requires Node.js (for `execjs` JS runtime) and Python 3.7+.

## Architecture

```
school_login.py          # CLI entry point — orchestrates login flow
portal.py                # Portal detection, API calls, network status
crypto.py                # RSA encryption via execjs
config.py                # User config CRUD (password.json), auto-detect, portal info persistence
gui.py                   # Tkinter GUI
rsa_full.js              # Third-party RSA big-integer library (David Shapiro, mod. Fuchun)
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
- `encrypt_password()` — runs `rsa_full.js` via `execjs`, implements the `{password}>{MAC}` + reverse + RSA pipeline

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

The encryption scheme is specific to 深澜 portals:

1. Concatenate: `{password}>{MAC}`
2. Reverse the entire string
3. RSA-encrypt with the portal's public key (exponent + modulus from `pageInfo`)
4. Remove spaces from the result

`rsa_full.js` attaches to `window`, so `encrypt_password()` replaces `})(window)` with `})(globalThis)` before feeding it to `execjs`. The JS engine needs to provide a `globalThis` — Node.js works.

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
- `rsa_full.js` is a static third-party file extracted from the portal page; if the portal updates its encryption, this file must be updated to match.
