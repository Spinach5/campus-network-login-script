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
school_login.py          # Main entry point — full login flow
rsa_full.js              # Third-party RSA big-integer library (David Shapiro, mod. Fuchun)
py/password.json         # User credentials (gitignored, use py/password.example.json as template)
requirements.txt         # pip dependencies
```

**Login flow in `school_login.py`:**

1. `get_redirect_info()` — GETs `http://www.baidu.com` without following redirects; the captive portal returns a 3xx with a `Location` header pointing to the full auth URL (includes `queryString`).
2. Parse `portal_base` (scheme+netloc) and `query_string` from the redirect URL.
3. `fetch_page_info()` — calls `/eportal/InterFace.do?method=pageInfo` (GET) to retrieve `publicKeyExponent`, `publicKeyModulus`, and other portal config.
4. `load_users()` / `select_user()` — load credentials from `py/password.json`, prompt user to pick one interactively.
5. `extract_mac_from_query()` — pulls the MAC address from the `queryString` (falls back to `DEFAULT_MAC = "111111111"`).
6. `encrypt_password()` — uses `execjs` to run `rsa_full.js` in-process. The password is combined with the MAC (`password>MAC`), reversed, then RSA-encrypted with the portal's public key.
7. `do_login()` — POSTs encrypted credentials to `/eportal/InterFace.do?method=login`.
8. Prints result — on success, outputs `userIndex` and `keepaliveInterval`.

Two generic API helpers wrap the portal endpoints: `_get_api()` and `_post_api()`. Both hit `/eportal/InterFace.do` with a `method` query param and return parsed JSON.

`get_online_user_info()` is defined but not called in the current `main()` flow — it exists as a utility for fetching the post-login redirect URL.

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
[{"name": "Display Name", "account": "student_id", "password": "plaintext_pwd", "server": "LT"}]
```

- `server`: ISP code — `LT` (联通), `YD` (移动), `DX` (电信)

## Notes

- `DETECT_URL` is `http://www.baidu.com` (not HTTPS) — captive portals intercept HTTP but pass HTTPS through.
- The `pageInfo` API (step 3) is a GET request, not HTML scraping. The `login` API is a POST.
- `rsa_full.js` is a static third-party file extracted from the portal page; if the portal updates its encryption, this file must be updated to match.
