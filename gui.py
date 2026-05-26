#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动登录 — 图形化界面
基于 tkinter，读取 py/password.json 展示账号卡片，支持登录/注销/添加账号操作。
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from portal import (
    check_network_status, detect_portal, do_login, do_logout,
    get_online_user_info,
)
from config import (
    add_portal_to_user_weblist, init_password_file, load_users,
    save_user_index, save_user_portal_info, save_users,
)
from crypto import encrypt_password


SERVER_MAP = {"LT": "联通", "YD": "移动", "DX": "电信"}
ISP_TO_CODE = {"移动": "YD", "联通": "LT", "电信": "DX"}


class AddAccountDialog:
    """添加账号的模态对话框"""

    def __init__(self, parent: tk.Tk):
        self.result = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("添加账号")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 居中定位
        self.dialog.update_idletasks()
        pw, ph = 320, 230
        px = parent.winfo_rootx() + (parent.winfo_width() - pw) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - ph) // 2
        self.dialog.geometry(f"{pw}x{ph}+{px}+{py}")

        frame = ttk.Frame(self.dialog, padding=16)
        frame.pack(fill="both", expand=True)

        # 名称
        ttk.Label(frame, text="名称:").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.name_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.name_var, width=28).grid(
            row=0, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))

        # 账户
        ttk.Label(frame, text="账户:").grid(row=1, column=0, sticky="w", pady=(0, 6))
        self.account_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.account_var, width=28).grid(
            row=1, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))

        # 密码
        ttk.Label(frame, text="密码:").grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.password_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.password_var, width=28, show="*").grid(
            row=2, column=1, sticky="ew", pady=(0, 6), padx=(8, 0))

        # 运营商
        ttk.Label(frame, text="运营商:").grid(row=3, column=0, sticky="w", pady=(0, 10))
        self.isp_var = tk.StringVar(value="移动")
        isp_combo = ttk.Combobox(frame, textvariable=self.isp_var,
                                 values=["移动", "联通", "电信"],
                                 state="readonly", width=26)
        isp_combo.grid(row=3, column=1, sticky="ew", pady=(0, 10), padx=(8, 0))

        # 按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(4, 0))
        ttk.Button(btn_frame, text="确认", width=10,
                   command=self._on_confirm).pack(side="left", padx=(30, 10))
        ttk.Button(btn_frame, text="取消", width=10,
                   command=self.dialog.destroy).pack(side="left", padx=(10, 30))

        self.dialog.bind("<Return>", lambda _: self._on_confirm())
        self.dialog.bind("<Escape>", lambda _: self.dialog.destroy())
        self.dialog.wait_window()

    def _on_confirm(self):
        name = self.name_var.get().strip()
        account = self.account_var.get().strip()
        password = self.password_var.get()
        isp = self.isp_var.get()

        if not account:
            messagebox.showwarning("提示", "请输入账户", parent=self.dialog)
            return
        if not password:
            messagebox.showwarning("提示", "请输入密码", parent=self.dialog)
            return

        self.result = {
            "name": name if name else account,
            "account": account,
            "password": password,
            "server": ISP_TO_CODE.get(isp, "YD"),
        }
        self.dialog.destroy()


class CampusNetworkApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("校园网自动登录")
        self.root.geometry("520x420")
        self.root.minsize(420, 320)
        self.root.resizable(True, True)

        # 状态
        self.portal_info = None
        self.online_user_index = None
        self.current_user_card = None
        self.users = []

        self._setup_ui()
        self._refresh_account_list()
        self._check_network()

    # ---------- UI 搭建 ----------
    def _setup_ui(self):
        # 标题
        title = ttk.Label(self.root, text="校园网自动登录", font=("", 16, "bold"))
        title.pack(pady=(12, 4))

        # 工具栏 — 左上角添加按钮
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=16, pady=(0, 4))
        add_btn = ttk.Button(toolbar, text="添加", width=6,
                             command=self._on_add_account)
        add_btn.pack(side="left")

        # 分割线
        ttk.Separator(self.root).pack(fill="x", padx=16)

        # 内容区域
        self.content = ttk.Frame(self.root)
        self.content.pack(fill="both", expand=True, padx=16, pady=8)

        # 空状态标签（初始不显示）
        self.empty_label = None

        # 滚动区域（有账号时使用）
        self.canvas = tk.Canvas(self.content, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.content, orient="vertical", command=self.canvas.yview)
        self.cards_frame = ttk.Frame(self.canvas)
        self.cards_frame.bind("<Configure>",
            lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # 鼠标滚轮
        self.canvas.bind("<Enter>", lambda _: self._bind_scroll())
        self.canvas.bind("<Leave>", lambda _: self._unbind_scroll())

        # 底部状态栏
        bottom = ttk.Frame(self.root)
        bottom.pack(side="bottom", fill="x")
        ttk.Separator(bottom).pack(fill="x")

        status_row = ttk.Frame(bottom)
        status_row.pack(fill="x")

        self.network_var = tk.StringVar(value="正在检测网络...")
        self.network_label = ttk.Label(status_row, textvariable=self.network_var,
                                       padding=(8, 3), foreground="gray")
        self.network_label.pack(side="left")

        self.action_var = tk.StringVar(value="")
        action_label = ttk.Label(status_row, textvariable=self.action_var,
                                 padding=(8, 3))
        action_label.pack(side="right")

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._canvas_window, width=event.width)

    def _bind_scroll(self):
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _unbind_scroll(self):
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
        self.canvas.unbind_all("<MouseWheel>")

    # ---------- 账号列表刷新 ----------
    def _refresh_account_list(self):
        """重新加载 password.json 并刷新界面"""
        self.users = load_users()

        # 清除现有内容
        for w in self.cards_frame.winfo_children():
            w.destroy()
        if self.empty_label:
            self.empty_label.destroy()
            self.empty_label = None

        # 隐藏滚动区域
        self.canvas.pack_forget()
        for child in self.content.winfo_children():
            if child != self.canvas:
                child.pack_forget()

        if not self.users:
            # 空状态
            self.empty_label = ttk.Label(
                self.content, text="没有任何账号",
                font=("", 18, "bold"), foreground="gray")
            self.empty_label.pack(expand=True)
            self.action_var.set("")
        else:
            # 显示账号卡片
            self.canvas.pack(side="left", fill="both", expand=True)
            self.scrollbar.pack(side="right", fill="y")
            for u in self.users:
                self._create_card(u)
            self.action_var.set("就绪 — 请选择账号登录")

    # ---------- 添加账号 ----------
    def _on_add_account(self):
        dialog = AddAccountDialog(self.root)
        if dialog.result:
            self.users.append(dialog.result)
            save_users(self.users)
            self._refresh_account_list()

    # ---------- 卡片组件 ----------
    def _create_card(self, user: dict):
        card = ttk.LabelFrame(self.cards_frame)
        card.pack(fill="x", pady=5)

        # 第一行：名称 + 按钮
        top_row = ttk.Frame(card)
        top_row.pack(fill="x", padx=10, pady=(8, 2))

        name_label = ttk.Label(top_row, text=user.get("name", "未命名"),
                               font=("", 12, "bold"))
        name_label.pack(side="left")

        btn = ttk.Button(top_row, text="登录", width=6)
        btn.pack(side="right")
        btn.config(command=lambda u=user: self._on_login_click(u))

        # 第二行：账号 + 运营商
        info_row = ttk.Frame(card)
        info_row.pack(fill="x", padx=10, pady=(0, 2))

        account_label = ttk.Label(info_row, text=f"账号: {user.get('account', '')}")
        account_label.pack(side="left")

        server = user.get("server", "LT")
        server_label = ttk.Label(info_row, text=f"运营商: {SERVER_MAP.get(server, server)}")
        server_label.pack(side="right", padx=(0, 10))

        # 第三行：状态
        status_label = ttk.Label(card, text="", foreground="gray", padding=(10, 0))
        status_label.pack(anchor="w", pady=(0, 6))

        user["_widgets"] = {
            "card": card,
            "btn": btn,
            "status_label": status_label,
            "name_label": name_label,
        }

    # ---------- 网络探测 ----------
    def _check_network(self):
        def run():
            try:
                status, portal_info, online_user = check_network_status()
            except Exception:
                status, portal_info, online_user = "未连接任何网络", None, None

            if portal_info:
                self.portal_info = portal_info

            color_map = {
                "已连接校园网": "green",
                "已连接校园网，暂未登录": "orange",
                "已连接网络(非校园网)": "#336699",
                "未连接任何网络": "red",
            }

            def update_ui():
                self.network_var.set(status)
                self.network_label.config(foreground=color_map.get(status, "gray"))

                if online_user:
                    u = online_user["user"]
                    info = online_user["info"]
                    self.online_user_index = info.get("userIndex")
                    self.current_user_card = u
                    svc = info.get("realServiceName", "")
                    isp_name = SERVER_MAP.get(svc, svc)
                    self.action_var.set(
                        f"当前在线: {u.get('name')} ({u.get('account')})"
                        f" | {isp_name}")
                    self._highlight_online_card(u)
                elif status == "已连接校园网，暂未登录":
                    if self.users:
                        self.action_var.set("就绪 — 请选择账号登录")
                elif status == "已连接网络(非校园网)":
                    self.action_var.set("非校园网环境，登录功能不可用")
                else:
                    self.action_var.set("请检查网络连接")

            self.root.after(0, update_ui)
        threading.Thread(target=run, daemon=True).start()

    def _highlight_online_card(self, online_user: dict):
        """将已在线用户的卡片标记为已登录状态。"""
        target_account = online_user.get("account", "")
        for u in self.users:
            widgets = u.get("_widgets")
            if not widgets:
                continue
            if u.get("account") == target_account:
                widgets["btn"].config(state="normal", text="注销",
                                      command=lambda u=u: self._on_logout_click(u))
                widgets["status_label"].config(text="已登录", foreground="green")
            else:
                widgets["btn"].config(state="disabled", text="登录")
                widgets["status_label"].config(text="已有其他账号在线", foreground="gray")

    # ---------- 登录流程 ----------
    def _on_login_click(self, user: dict):
        if not self.portal_info:
            messagebox.showwarning("提示", "网络尚未检测完成，请稍后再试")
            return

        if self.online_user_index is not None:
            messagebox.showwarning("提示", "已有账号在线，请先注销后再切换账号")
            return

        # portal_info: (portal_base, query_string, exponent, modulus, mac)
        exponent = self.portal_info[2]
        modulus = self.portal_info[3]

        # 如果 portal_info 来自已保存 portal 检测，缺少 RSA 密钥，需要重新探测
        if not exponent or not modulus:
            widgets = user["_widgets"]
            widgets["btn"].config(state="disabled", text="...")
            widgets["status_label"].config(text="正在探测 Portal...", foreground="blue")
            self.action_var.set("重新探测 Portal 认证信息...")
            self._re_detect_and_login(user)
            return

        self._do_login(user)

    def _re_detect_and_login(self, user: dict):
        """重新探测 Portal 获取 RSA 密钥后再登录。"""
        def run():
            try:
                new_info = detect_portal()
                self.portal_info = new_info
                self.root.after(0, lambda: self._do_login(user))
            except Exception as e:
                self.root.after(0, lambda: self._on_login_fail(user, f"Portal 探测失败: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _do_login(self, user: dict):
        """执行实际的登录请求。"""
        widgets = user["_widgets"]
        widgets["btn"].config(state="disabled", text="...")
        widgets["status_label"].config(text="正在登录...", foreground="blue")
        self.action_var.set(f"正在登录 {user.get('name')}...")

        def run():
            try:
                portal_base, query_string, exponent, modulus, mac = self.portal_info
                encrypted = encrypt_password(user["password"], mac, exponent, modulus)
                result = do_login(portal_base, user["account"], encrypted,
                                  user.get("server", "LT"), query_string)
                if result.get("result") == "success":
                    user_index = result.get("userIndex")
                    self.root.after(0, lambda: self._on_login_ok(user, user_index))
                else:
                    err = result.get("message", "未知错误")
                    self.root.after(0, lambda: self._on_login_fail(user, err))
            except Exception as e:
                self.root.after(0, lambda: self._on_login_fail(user, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_login_ok(self, user: dict, user_index: str):
        self.online_user_index = user_index
        self.current_user_card = user

        # 高亮当前用户卡片，禁用其他
        self._highlight_online_card(user)

        self.action_var.set(f"{user.get('name')} 登录成功")
        self.network_var.set("已连接校园网")
        self.network_label.config(foreground="green")

        # 保存 Portal 地址、userIndex 和用户详细信息
        if self.portal_info:
            portal_base = self.portal_info[0]
            add_portal_to_user_weblist(user["account"], portal_base)
            save_user_index(user["account"], user_index)
            self._fetch_and_save_portal_info(user["account"], portal_base, user_index)

        messagebox.showinfo("登录成功", f"{user.get('name')} 登录成功！")

    def _fetch_and_save_portal_info(self, account: str, portal_base: str,
                                     user_index: str):
        """后台线程：获取在线用户信息并保存到本地配置。"""
        def run():
            info = get_online_user_info(portal_base, user_index)
            if info:
                save_user_portal_info(account, info)
        threading.Thread(target=run, daemon=True).start()

    def _on_login_fail(self, user: dict, error: str):
        widgets = user["_widgets"]
        widgets["btn"].config(state="normal", text="登录")
        widgets["status_label"].config(text=f"登录失败: {error}", foreground="red")
        self.action_var.set(f"登录失败: {error}")

    # ---------- 注销流程 ----------
    def _on_logout_click(self, user: dict):
        if not messagebox.askyesno("确认注销", "是否退出登录?"):
            return

        if not self.portal_info or not self.online_user_index:
            messagebox.showwarning("提示", "未登录或网络信息丢失")
            return

        widgets = user["_widgets"]
        widgets["btn"].config(state="disabled", text="...")
        widgets["status_label"].config(text="正在注销...", foreground="blue")
        self.action_var.set(f"正在注销 {user.get('name')}...")

        user_index = self.online_user_index

        def run():
            try:
                portal_base = self.portal_info[0]
                result = do_logout(portal_base, user_index)
                if result.get("result") == "success":
                    self.root.after(0, lambda: self._on_logout_ok(user))
                else:
                    err = result.get("message", "未知错误")
                    self.root.after(0, lambda: self._on_logout_fail(user, err))
            except Exception as e:
                self.root.after(0, lambda: self._on_logout_fail(user, str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_logout_ok(self, user: dict):
        self.online_user_index = None
        self.current_user_card = None

        # 重置所有卡片状态
        for u in self.users:
            w = u.get("_widgets")
            if not w:
                continue
            w["btn"].config(state="normal", text="登录",
                            command=lambda u=u: self._on_login_click(u))
            w["status_label"].config(text="", foreground="gray")

        self.action_var.set(f"{user.get('name')} 已注销")
        self.network_var.set("已连接校园网，暂未登录")
        self.network_label.config(foreground="orange")

        # 重新检测网络，获取完整 Portal 信息（RSA 密钥等）
        self._check_network()

        messagebox.showinfo("注销成功", "已退出登录")

    def _on_logout_fail(self, user: dict, error: str):
        widgets = user["_widgets"]
        widgets["btn"].config(state="normal", text="注销")
        widgets["status_label"].config(text=f"注销失败: {error}", foreground="red")
        self.action_var.set(f"注销失败: {error}")


def launch_gui():
    init_password_file()
    root = tk.Tk()
    CampusNetworkApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
