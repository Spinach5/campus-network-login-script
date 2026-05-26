#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
校园网自动登录 — 图形化界面
基于 tkinter，读取 py/password.json 展示账号卡片，支持登录/注销操作。
"""

import threading
import tkinter as tk
from tkinter import ttk, messagebox

from school_login import check_network_status, do_login, do_logout, encrypt_password, load_users


SERVER_MAP = {"LT": "联通", "YD": "移动", "DX": "电信"}


class CampusNetworkApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("校园网自动登录")
        self.root.geometry("520x420")
        self.root.minsize(420, 320)
        self.root.resizable(True, True)

        # 状态
        self.portal_info = None          # (portal_base, query_string, exponent, modulus, mac)
        self.online_user_index = None    # 当前在线用户的 userIndex
        self.current_user_card = None    # 当前在线用户对应的卡片 dict

        self._setup_ui()
        self._load_users()
        self._check_network()

    # ---------- UI 搭建 ----------
    def _setup_ui(self):
        # 标题
        title = ttk.Label(self.root, text="校园网自动登录", font=("", 16, "bold"))
        title.pack(pady=(12, 6))

        # 分割线
        ttk.Separator(self.root).pack(fill="x", padx=16)

        # 滚动区域 — 卡片列表
        container = ttk.Frame(self.root)
        container.pack(fill="both", expand=True, padx=16, pady=8)

        self.canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.canvas.yview)
        self.cards_frame = ttk.Frame(self.canvas)

        self.cards_frame.bind("<Configure>",
            lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        # 让卡片区域宽度跟随 canvas
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 鼠标滚轮支持
        self.canvas.bind("<Enter>", lambda _: self._bind_scroll())
        self.canvas.bind("<Leave>", lambda _: self._unbind_scroll())

        # 底部状态栏
        bottom = ttk.Frame(self.root)
        bottom.pack(side="bottom", fill="x")
        ttk.Separator(bottom).pack(fill="x")

        status_row = ttk.Frame(bottom)
        status_row.pack(fill="x")

        # 左下角：网络状态
        self.network_var = tk.StringVar(value="正在检测网络...")
        self.network_label = ttk.Label(status_row, textvariable=self.network_var,
                                       padding=(8, 3), foreground="gray")
        self.network_label.pack(side="left")

        # 右下角：操作状态
        self.action_var = tk.StringVar(value="")
        action_label = ttk.Label(status_row, textvariable=self.action_var,
                                 padding=(8, 3))
        action_label.pack(side="right")

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self._canvas_window, width=event.width)

    def _bind_scroll(self):
        # Linux: Button-4/5
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        # Windows/Mac: MouseWheel
        self.canvas.bind_all("<MouseWheel>",
            lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

    def _unbind_scroll(self):
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")
        self.canvas.unbind_all("<MouseWheel>")

    # ---------- 数据加载 ----------
    def _load_users(self):
        try:
            users = load_users()
        except Exception as e:
            self.action_var.set(f"加载配置失败: {e}")
            empty = ttk.Label(self.cards_frame, text="未找到 py/password.json，请先创建配置文件。",
                              foreground="gray")
            empty.pack(pady=20)
            return

        if not users:
            self.action_var.set("配置文件中没有账号")
            return

        for u in users:
            self._create_card(u)

        self.action_var.set("就绪 — 请选择账号登录")

    # ---------- 卡片组件 ----------
    def _create_card(self, user: dict):
        """为单个用户创建卡片，包含信息区、按钮区和状态区"""
        card = ttk.LabelFrame(self.cards_frame)
        card.pack(fill="x", pady=5)

        # 第一行：名称 + 按钮
        top_row = ttk.Frame(card)
        top_row.pack(fill="x", padx=10, pady=(8, 2))

        name_label = ttk.Label(top_row, text=user.get("name", "未命名"),
                               font=("", 12, "bold"))
        name_label.pack(side="left")

        # 按钮 — 初始为"登录"
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

        # 保存引用
        user["_widgets"] = {
            "card": card,
            "btn": btn,
            "status_label": status_label,
            "name_label": name_label,
        }

    # ---------- 网络探测 ----------
    def _check_network(self):
        """后台线程：检测网络状态并更新 UI"""
        def run():
            try:
                status, portal_info = check_network_status()
            except Exception:
                status, portal_info = "未连接任何网络", None

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

                if status in ("已连接校园网", "已连接校园网，暂未登录"):
                    self.action_var.set("就绪 — 请选择账号登录")
                elif status == "已连接网络(非校园网)":
                    self.action_var.set("非校园网环境，登录功能不可用")
                else:
                    self.action_var.set("请检查网络连接")

            self.root.after(0, update_ui)
        threading.Thread(target=run, daemon=True).start()

    # ---------- 登录流程 ----------
    def _on_login_click(self, user: dict):
        if not self.portal_info:
            messagebox.showwarning("提示", "网络尚未检测完成，请稍后再试")
            return

        if self.online_user_index is not None:
            messagebox.showwarning("提示", "已有账号在线，请先注销后再切换账号")
            return

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

        widgets = user["_widgets"]
        widgets["btn"].config(state="normal", text="注销",
                              command=lambda u=user: self._on_logout_click(u))
        widgets["status_label"].config(text="已登录", foreground="green")
        self.action_var.set(f"{user.get('name')} 登录成功")
        self.network_var.set("已连接校园网")
        self.network_label.config(foreground="green")

        messagebox.showinfo("登录成功", f"{user.get('name')} 登录成功！")

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

        widgets = user["_widgets"]
        widgets["btn"].config(state="normal", text="登录",
                              command=lambda u=user: self._on_login_click(u))
        widgets["status_label"].config(text="", foreground="gray")
        self.action_var.set(f"{user.get('name')} 已注销")
        self.network_var.set("已连接校园网，暂未登录")
        self.network_label.config(foreground="orange")

        messagebox.showinfo("注销成功", "已退出登录")

    def _on_logout_fail(self, user: dict, error: str):
        widgets = user["_widgets"]
        widgets["btn"].config(state="normal", text="注销")
        widgets["status_label"].config(text=f"注销失败: {error}", foreground="red")
        self.action_var.set(f"注销失败: {error}")


def launch_gui():
    root = tk.Tk()
    CampusNetworkApp(root)
    root.mainloop()


if __name__ == "__main__":
    launch_gui()
