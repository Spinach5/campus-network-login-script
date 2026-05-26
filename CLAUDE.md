# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

校园网 (campus network) captive portal auto-login script. Detects the portal redirect, fetches RSA public key parameters from the login page, encrypts the password in-browser-style via `execjs`, and submits the authentication request.

## Architecture

```
school_login.py          # Main entry point — orchestrates the full login flow
rsa_full.js              # RSA big-integer implementation (BigInt, Barrett reduction, RSA key pair)
py/password.json         # User credentials: [{name, account, password, server}, ...]
```

**Login flow in `school_login.py`:**

1. `get_redirect_info()` — GETs `http://www.baidu.com` without following redirects; the captive portal returns a 3xx with a `Location` header pointing to the full auth URL.
2. `fetch_rsa_and_query()` — Parses the auth page HTML for `publicKeyModulus`, `publicKeyExponent`, and `queryString` (which encodes the original destination + MAC address).
3. `encrypt_password()` — Uses `execjs` to run `rsa_full.js` in-process. The password is combined with the MAC (`password>MAC`), reversed, then RSA-encrypted with the portal's public key.
4. `do_login()` — POSTs encrypted credentials to `/eportal/InterFace.do?method=login`.
5. `get_online_user_info()` — After successful auth, fetches the redirect URL to reach the internet.

The RSA encryption scheme is specific to 深澜 (Srun) portal systems.

## Dependencies

- Python 3 with `requests` and `PyExecJS` (`execjs`)
- A JS runtime available to `execjs` (typically Node.js or PyV8)

## Usage

```bash
python3 school_login.py
```

The script interactively prompts for user selection from `py/password.json`.

## Password config format

`py/password.json` is a JSON array of objects:
```json
[{"name": "Display Name", "account": "student_id", "password": "plaintext_pwd", "server": "LT"}]
```
- `server`: ISP code — `LT` (联通), `YD` (移动), `DX` (电信)

## Notes

- The hardcoded `DETECT_URL` is `http://www.baidu.com` (not HTTPS) — captive portals typically intercept HTTP requests but pass HTTPS through.
- `DEFAULT_MAC` (`111111111`) is used as a fallback when no MAC can be extracted from the query string.
- `rsa_full.js` is a third-party RSA library (David Shapiro, modified by Fuchun). It attaches to `window`, so `execjs` needs a JS engine that provides a `window` global — Node.js works with minor polyfilling, but the current code relies on `execjs`'s environment handling.
