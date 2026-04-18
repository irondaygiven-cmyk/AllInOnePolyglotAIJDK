#!/usr/bin/env python3
"""
AIJDK_Manager.py  –  AllInOnePolyglotAIJDK  Persistent Manager Window
=======================================================================
Single-file launcher that opens a dark-themed tkinter window (stdlib only,
no external deps required) and manages the entire lifecycle:

  1. Install / verify dependencies  (creates .venv, installs wheels)
  2. Link Models via Directory Junction  (mklink /J — no elevation required,
     fixes the "Access is denied" issue that occurs with mklink /D symlinks)
  3. Launch the main AIJDK UI  (AllInOnePolyglotAIJDK.py in the venv)

Usage:
  python AIJDK_Manager.py
  — or double-click AIJDK_Manager.bat —
"""

import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_VENV_DIR   = os.path.join(_SCRIPT_DIR, ".venv")
_VENV_PY    = os.path.join(_VENV_DIR, "Scripts", "python.exe")
_VENV_PIP   = os.path.join(_VENV_DIR, "Scripts", "pip.exe")
_MAIN_PY    = os.path.join(_SCRIPT_DIR, "AllInOnePolyglotAIJDK.py")
_SLINT_PY   = os.path.join(_SCRIPT_DIR, "SlintAIJDK.py")

# Wheels bundled in the repo root
_BUNDLED_WHEELS = [
    "setuptools-82.0.1-py3-none-any.whl",
    "huggingface_hub-0.36.2-py3-none-any.whl",
    "llama_cpp_python-0.1.66+cu121-cp311-cp311-win_amd64.whl",
    "torchvision-0.21.0-cp311-cp311-win_amd64.whl",
]

# External-wheels base directory (user can change this in the UI)
_DEFAULT_EXT_WHEELS = r"H:\Models-D1\wheels"
_EXT_WHEELS = [
    "pip-26.0.1-py3-none-any.whl",
    "idna-3.11-py3-none-any.whl",
    "numpy-1.26.4-cp311-cp311-win_amd64.whl",
    "ml_dtypes-0.5.4-cp311-cp311-win_amd64.whl",
    "pillow-10.4.0-cp311-cp311-win_amd64.whl",
    "kiwisolver-1.5.0-cp311-cp311-win_amd64.whl",
    "fonttools-4.62.1-cp311-cp311-win_amd64.whl",
    "cython-3.2.4-cp311-cp311-win_amd64.whl",
    "tokenizers-0.19.1-cp311-none-win_amd64.whl",
    "transformers-4.44.0-py3-none-any.whl",
    "diffusers-0.30.0-py3-none-any.whl",
    "xformers-0.0.35-py39-none-win_amd64.whl",
    "mediapipe-0.10.33-py3-none-win_amd64.whl",
    "pywin32-311-cp311-cp311-win_amd64.whl",
    "flask-3.1.3-py3-none-any.whl",
    "flask_cors-6.0.2-py3-none-any.whl",
    "fastapi-0.115.0-py3-none-any.whl",
    "onnx-1.21.0-cp311-cp311-win_amd64.whl",
    "onnxruntime-1.24.4-cp311-cp311-win_amd64.whl",
]

# Default model junction paths
_DEFAULT_LINK_SRC  = r"D:\UI\models"
_DEFAULT_LINK_REPO = r"C:\UI\Local-diffusion-host_UI"

# ---------------------------------------------------------------------------
# Colours / fonts
# ---------------------------------------------------------------------------
BG       = "#0a0a0a"
PANEL    = "#111111"
ACCENT   = "#00ff9d"
FG       = "#e0e0e0"
FG_DIM   = "#666666"
FG_ERR   = "#ff4444"
FG_WARN  = "#ffcc00"
BTN_BG   = "#1a2a1a"
BTN_ACT  = "#00cc7a"
FONT_UI  = ("Segoe UI", 10)
FONT_LOG = ("Consolas", 9)


# ---------------------------------------------------------------------------
# Manager application
# ---------------------------------------------------------------------------
class ManagerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self._busy = False
        self._app_proc: subprocess.Popen | None = None
        self._slint_proc: subprocess.Popen | None = None

        self._build_ui()
        self._refresh_status()

    # ------------------------------------------------------------------ UI --

    def _build_ui(self):
        root = self.root
        root.title("AllInOnePolyglotAIJDK  –  Manager")
        root.configure(bg=BG)
        root.geometry("1100x700")
        root.minsize(800, 500)

        # ── Top title bar ────────────────────────────────────────────────────
        title_frame = tk.Frame(root, bg=PANEL, height=48)
        title_frame.pack(fill="x", side="top")
        tk.Label(
            title_frame,
            text="  ◈  AllInOnePolyglotAIJDK  –  Manager",
            bg=PANEL, fg=ACCENT,
            font=("Segoe UI", 13, "bold"),
            anchor="w",
        ).pack(side="left", padx=16, pady=10)

        self._status_lbl = tk.Label(
            title_frame, text="●  Idle", bg=PANEL, fg=FG_DIM,
            font=("Segoe UI", 10),
        )
        self._status_lbl.pack(side="right", padx=16)

        # ── Notebook (tabs) ──────────────────────────────────────────────────
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",       background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",   background=PANEL, foreground=FG,
                        padding=[14, 6],   font=FONT_UI)
        style.map("TNotebook.Tab",
                  background=[("selected", BTN_BG)],
                  foreground=[("selected", ACCENT)])

        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        self._tab_setup  = self._make_tab(nb, "⚙  Setup & Install")
        self._tab_models = self._make_tab(nb, "🔗  Model Junctions")
        self._tab_launch = self._make_tab(nb, "🚀  Launch UI")
        self._tab_log    = self._make_tab(nb, "📋  Full Log")

        self._build_setup_tab(self._tab_setup)
        self._build_models_tab(self._tab_models)
        self._build_launch_tab(self._tab_launch)
        self._build_log_tab(self._tab_log)

    @staticmethod
    def _make_tab(nb, label):
        frame = tk.Frame(nb, bg=BG)
        nb.add(frame, text=label)
        return frame

    # ── Setup tab ──────────────────────────────────────────────────────────

    def _build_setup_tab(self, parent):
        # External wheels directory
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=16, pady=(16, 4))
        tk.Label(row, text="External wheels directory:", bg=BG, fg=FG,
                 font=FONT_UI).pack(side="left")
        self._ext_wheels_var = tk.StringVar(value=_DEFAULT_EXT_WHEELS)
        tk.Entry(row, textvariable=self._ext_wheels_var, bg=PANEL, fg=FG,
                 insertbackground=ACCENT, font=FONT_UI, width=42).pack(side="left", padx=8)
        tk.Button(row, text="Browse", command=self._browse_ext_wheels,
                  bg=BTN_BG, fg=ACCENT, font=FONT_UI, relief="flat",
                  activebackground=BTN_ACT).pack(side="left")

        # Status grid
        self._setup_status = tk.Text(parent, bg=PANEL, fg=FG, font=FONT_LOG,
                                     height=6, state="disabled", relief="flat",
                                     padx=10, pady=8)
        self._setup_status.pack(fill="x", padx=16, pady=8)

        btn_row = tk.Frame(parent, bg=BG)
        btn_row.pack(pady=4)
        self._btn_install = self._btn(btn_row, "Install / Verify Dependencies",
                                      self._do_install)
        self._btn_install.pack(side="left", padx=6)

        # Mini log
        tk.Label(parent, text="Output:", bg=BG, fg=FG_DIM,
                 font=FONT_UI).pack(anchor="w", padx=16)
        self._setup_log = self._logbox(parent)

    def _browse_ext_wheels(self):
        d = filedialog.askdirectory(title="Select external wheels directory",
                                    initialdir=self._ext_wheels_var.get())
        if d:
            self._ext_wheels_var.set(d.replace("/", "\\"))

    # ── Models tab ─────────────────────────────────────────────────────────

    def _build_models_tab(self, parent):
        info = tk.Label(
            parent,
            text=(
                "Directory junctions (mklink /J) are used instead of symlinks\n"
                "so that no administrator elevation or Developer Mode is required."
            ),
            bg=BG, fg=ACCENT, font=("Segoe UI", 10, "italic"), justify="left",
        )
        info.pack(anchor="w", padx=16, pady=(14, 4))

        # Source directory (models on another drive)
        row1 = tk.Frame(parent, bg=BG)
        row1.pack(fill="x", padx=16, pady=4)
        tk.Label(row1, text="Models source directory:", bg=BG, fg=FG,
                 font=FONT_UI, width=26, anchor="w").pack(side="left")
        self._link_src_var = tk.StringVar(value=_DEFAULT_LINK_SRC)
        tk.Entry(row1, textvariable=self._link_src_var, bg=PANEL, fg=FG,
                 insertbackground=ACCENT, font=FONT_UI, width=40).pack(side="left", padx=8)
        tk.Button(row1, text="Browse", command=lambda: self._browse_dir(self._link_src_var),
                  bg=BTN_BG, fg=ACCENT, font=FONT_UI, relief="flat",
                  activebackground=BTN_ACT).pack(side="left")

        # Repo directory (junction target lives at <repo>\models\)
        row2 = tk.Frame(parent, bg=BG)
        row2.pack(fill="x", padx=16, pady=4)
        tk.Label(row2, text="Repo directory:", bg=BG, fg=FG,
                 font=FONT_UI, width=26, anchor="w").pack(side="left")
        self._link_repo_var = tk.StringVar(value=_DEFAULT_LINK_REPO)
        tk.Entry(row2, textvariable=self._link_repo_var, bg=PANEL, fg=FG,
                 insertbackground=ACCENT, font=FONT_UI, width=40).pack(side="left", padx=8)
        tk.Button(row2, text="Browse", command=lambda: self._browse_dir(self._link_repo_var),
                  bg=BTN_BG, fg=ACCENT, font=FONT_UI, relief="flat",
                  activebackground=BTN_ACT).pack(side="left")

        btn_row = tk.Frame(parent, bg=BG)
        btn_row.pack(pady=8)
        self._btn_link = self._btn(btn_row, "Create Model Junctions",
                                   self._do_link_models)
        self._btn_link.pack(side="left", padx=6)

        tk.Label(parent, text="Output:", bg=BG, fg=FG_DIM,
                 font=FONT_UI).pack(anchor="w", padx=16)
        self._link_log = self._logbox(parent)

    def _browse_dir(self, var: tk.StringVar):
        d = filedialog.askdirectory(title="Select directory", initialdir=var.get())
        if d:
            var.set(d.replace("/", "\\"))

    # ── Launch tab ─────────────────────────────────────────────────────────

    def _build_launch_tab(self, parent):
        info = tk.Label(
            parent,
            text="Launches AllInOnePolyglotAIJDK.py inside the managed virtual environment.",
            bg=BG, fg=FG, font=FONT_UI,
        )
        info.pack(pady=(20, 8))

        self._venv_lbl = tk.Label(parent, text="", bg=BG, fg=FG_DIM, font=FONT_UI)
        self._venv_lbl.pack()

        btn_row = tk.Frame(parent, bg=BG)
        btn_row.pack(pady=12)
        self._btn_launch = self._btn(btn_row, "Launch AIJDK UI (PySide6)", self._do_launch)
        self._btn_launch.pack(side="left", padx=6)
        self._btn_stop = self._btn(btn_row, "Stop PySide6", self._do_stop,
                                   fg=FG_ERR, state="disabled")
        self._btn_stop.pack(side="left", padx=6)

        slint_row = tk.Frame(parent, bg=BG)
        slint_row.pack(pady=4)
        self._btn_launch_slint = self._btn(slint_row, "Launch AIJDK UI (Slint)",
                                           self._do_launch_slint)
        self._btn_launch_slint.pack(side="left", padx=6)
        self._btn_stop_slint = self._btn(slint_row, "Stop Slint", self._do_stop_slint,
                                         fg=FG_ERR, state="disabled")
        self._btn_stop_slint.pack(side="left", padx=6)

        tk.Label(parent, text="Output:", bg=BG, fg=FG_DIM,
                 font=FONT_UI).pack(anchor="w", padx=16)
        self._launch_log = self._logbox(parent)

    # ── Full log tab ────────────────────────────────────────────────────────

    def _build_log_tab(self, parent):
        self._full_log = self._logbox(parent, expand=True)

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _btn(parent, text, cmd, fg=ACCENT, state="normal"):
        return tk.Button(
            parent, text=text, command=cmd,
            bg=BTN_BG, fg=fg, activeforeground=BTN_ACT,
            activebackground=PANEL, font=("Segoe UI", 10, "bold"),
            relief="flat", padx=14, pady=7, state=state,
        )

    def _logbox(self, parent, expand=False):
        frame = tk.Frame(parent, bg=PANEL)
        pack_opts = dict(fill="both", padx=16, pady=(2, 10))
        if expand:
            pack_opts["expand"] = True
        frame.pack(**pack_opts)

        sb = tk.Scrollbar(frame)
        sb.pack(side="right", fill="y")

        box = tk.Text(frame, bg="#0d0d0d", fg=FG, font=FONT_LOG,
                      insertbackground=ACCENT, yscrollcommand=sb.set,
                      state="disabled", relief="flat", padx=8, pady=6)
        box.pack(side="left", fill="both", expand=True)
        sb.config(command=box.yview)

        box.tag_config("err",  foreground=FG_ERR)
        box.tag_config("ok",   foreground=ACCENT)
        box.tag_config("warn", foreground=FG_WARN)
        box.tag_config("dim",  foreground=FG_DIM)
        return box

    def _log(self, box: tk.Text, msg: str, tag: str | None = None):
        """Append a line to a log widget (thread-safe via after)."""
        def _do():
            box.configure(state="normal")
            box.insert("end", msg + "\n", tag or "")
            box.see("end")
            box.configure(state="disabled")
            # mirror to full log
            if box is not self._full_log:
                self._full_log.configure(state="normal")
                self._full_log.insert("end", msg + "\n", tag or "")
                self._full_log.see("end")
                self._full_log.configure(state="disabled")
        self.root.after(0, _do)

    def _set_status(self, text: str, colour: str = FG_DIM):
        self.root.after(0, lambda: self._status_lbl.config(text=text, fg=colour))

    def _refresh_status(self):
        venv_ok = os.path.isfile(_VENV_PY)
        if venv_ok:
            self._venv_lbl.config(text=f"Virtual environment: {_VENV_DIR}", fg=ACCENT)
        else:
            self._venv_lbl.config(text="Virtual environment: NOT FOUND — run Setup first",
                                  fg=FG_ERR)
        # Disable/enable launch
        state = "normal" if venv_ok else "disabled"
        self._btn_launch.config(state=state)
        self._btn_launch_slint.config(state=state)

    def _set_busy(self, busy: bool, btn: tk.Button | None = None):
        self._busy = busy
        self._set_status("●  Running…" if busy else "●  Idle",
                         ACCENT if busy else FG_DIM)
        for b in (self._btn_install, self._btn_link, self._btn_launch,
                  self._btn_launch_slint):
            b.config(state="disabled" if busy else "normal")
        if not busy:
            self._refresh_status()

    def _update_setup_status_box(self):
        venv_ok   = os.path.isfile(_VENV_PY)
        main_ok   = os.path.isfile(_MAIN_PY)
        box = self._setup_status
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("end", f"Virtual environment : {_VENV_DIR}\n",
                   "ok" if venv_ok else "err")
        box.insert("end", f"  pip              : {'found' if os.path.isfile(_VENV_PIP) else 'missing'}\n",
                   "ok" if os.path.isfile(_VENV_PIP) else "err")
        box.insert("end", f"Main script        : {'found' if main_ok else 'missing'}\n",
                   "ok" if main_ok else "err")
        ext_dir = self._ext_wheels_var.get()
        box.insert("end", f"External wheels dir: {ext_dir}\n",
                   "ok" if os.path.isdir(ext_dir) else "warn")
        box.configure(state="disabled")

    # ---------------------------------------------------------------- Actions

    # ── 1. Install ────────────────────────────────────────────────────────

    def _do_install(self):
        if self._busy:
            return
        self._set_busy(True, self._btn_install)
        self._update_setup_status_box()
        threading.Thread(target=self._install_worker, daemon=True).start()

    def _install_worker(self):
        log = self._setup_log

        def out(msg, tag=None):
            self._log(log, msg, tag)

        out("=== AllInOnePolyglotAIJDK  –  Dependency Setup ===", "ok")

        # Check Python
        try:
            r = subprocess.run(["python", "--version"], capture_output=True, text=True)
            out(f"Python: {r.stdout.strip() or r.stderr.strip()}", "ok")
        except FileNotFoundError:
            out("ERROR: python not found on PATH.", "err")
            self._set_busy(False)
            return

        # Create venv
        if not os.path.isfile(_VENV_PY):
            out("Creating virtual environment…")
            try:
                import venv as _venv
                _venv.create(_VENV_DIR, with_pip=True)
                out("Virtual environment created.", "ok")
            except Exception as e:
                out(f"ERROR creating venv: {e}", "err")
                self._set_busy(False)
                return
        else:
            out("Virtual environment already exists.", "dim")

        ext_base = self._ext_wheels_var.get()

        def pip(*args):
            cmd = [_VENV_PIP, *args]
            out(f"> pip {' '.join(args)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout.strip():
                out(result.stdout.strip())
            if result.returncode != 0:
                out(result.stderr.strip(), "err")
                return False
            return True

        # pip self-upgrade from external wheel if present
        ext_pip = os.path.join(ext_base, "pip-26.0.1-py3-none-any.whl")
        if os.path.isfile(ext_pip):
            pip("install", ext_pip)
        pip("install", "--upgrade", "pip", "wheel")

        # PySide6 + requests + slint (online)
        out("Installing PySide6, requests, and slint…")
        pip("install", "PySide6", "requests", "slint")

        # Bundled wheels
        for whl in _BUNDLED_WHEELS:
            path = os.path.join(_SCRIPT_DIR, whl)
            if os.path.isfile(path):
                pip("install", path)
            else:
                out(f"  Bundled wheel not found (skip): {whl}", "warn")

        # External wheels
        for whl in _EXT_WHEELS:
            if whl.startswith("pip-"):
                continue  # already handled
            path = os.path.join(ext_base, whl)
            if os.path.isfile(path):
                pip("install", path)
            else:
                out(f"  External wheel not found (skip): {whl}", "warn")

        out("")
        out("Installation complete.", "ok")
        self._set_busy(False)
        self.root.after(0, self._update_setup_status_box)

    # ── 2. Model junctions ────────────────────────────────────────────────

    def _do_link_models(self):
        if self._busy:
            return
        self._set_busy(True, self._btn_link)
        threading.Thread(target=self._link_worker, daemon=True).start()

    def _link_worker(self):
        log = self._link_log

        def out(msg, tag=None):
            self._log(log, msg, tag)

        src  = self._link_src_var.get().rstrip("\\")
        repo = self._link_repo_var.get().rstrip("\\")
        tgt_models = os.path.join(repo, "models")

        out("=== Model Junction Setup ===", "ok")
        out(f"  Source : {src}")
        out(f"  Target : {tgt_models}")
        out("")

        if not os.path.isdir(src):
            out(f"ERROR: source directory not found: {src}", "err")
            self._set_busy(False)
            return

        if not os.path.isdir(repo):
            out(f"ERROR: repo directory not found: {repo}", "err")
            self._set_busy(False)
            return

        os.makedirs(tgt_models, exist_ok=True)

        entries = [e for e in os.scandir(src) if e.is_dir(follow_symlinks=False)]
        if not entries:
            out("No subdirectories found in source — nothing to link.", "warn")
            self._set_busy(False)
            return

        ok_count = skip_count = err_count = 0
        for entry in entries:
            name  = entry.name
            link  = os.path.join(tgt_models, name)

            if os.path.exists(link) or os.path.islink(link):
                out(f"  [skip]  {name}  (already exists)", "dim")
                skip_count += 1
                continue

            # mklink /J creates a directory junction — no elevation needed
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", link, entry.path],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                out(f"  [ok]    {name}", "ok")
                ok_count += 1
            else:
                err_msg = (result.stderr or result.stdout).strip()
                out(f"  [FAIL]  {name}  —  {err_msg}", "err")
                err_count += 1

        out("")
        summary_tag = "ok" if err_count == 0 else "warn"
        out(f"Done: {ok_count} linked, {skip_count} skipped, {err_count} failed.",
            summary_tag)
        self._set_busy(False)

    # ── 3. Launch AIJDK UI ────────────────────────────────────────────────

    def _do_launch(self):
        if self._busy:
            return
        if not os.path.isfile(_VENV_PY):
            messagebox.showerror("Virtual environment not found",
                                 "Please run Setup & Install first.")
            return
        if self._app_proc and self._app_proc.poll() is None:
            messagebox.showinfo("Already running", "The AIJDK UI is already running.")
            return

        self._set_busy(True, self._btn_launch)
        self._btn_stop.config(state="normal")
        threading.Thread(target=self._launch_worker, daemon=True).start()

    def _launch_worker(self):
        log = self._launch_log

        def out(msg, tag=None):
            self._log(log, msg, tag)

        out("=== Launching AllInOnePolyglotAIJDK UI ===", "ok")
        out(f"  Python : {_VENV_PY}")
        out(f"  Script : {_MAIN_PY}")
        out("")

        try:
            self._app_proc = subprocess.Popen(
                [_VENV_PY, _MAIN_PY],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=_SCRIPT_DIR,
            )

            for line in self._app_proc.stdout:
                tag = "err" if line.lower().startswith("error") else None
                out(line.rstrip(), tag)

            self._app_proc.wait()
            exit_code = self._app_proc.returncode
            tag = "ok" if exit_code == 0 else "err"
            out(f"\nProcess exited (code {exit_code}).", tag)
        except Exception as e:
            out(f"ERROR: {e}", "err")
        finally:
            self.root.after(0, lambda: self._btn_stop.config(state="disabled"))
            self._set_busy(False)

    def _do_stop(self):
        if self._app_proc and self._app_proc.poll() is None:
            self._app_proc.terminate()
            self._log(self._launch_log, "Stop requested.", "warn")
        self._btn_stop.config(state="disabled")

    # ── 4. Launch Slint UI ────────────────────────────────────────────────

    def _do_launch_slint(self):
        if self._busy:
            return
        if not os.path.isfile(_VENV_PY):
            messagebox.showerror("Virtual environment not found",
                                 "Please run Setup & Install first.")
            return
        if not os.path.isfile(_SLINT_PY):
            messagebox.showerror("SlintAIJDK.py not found",
                                 f"Could not find:\n{_SLINT_PY}")
            return
        if self._slint_proc and self._slint_proc.poll() is None:
            messagebox.showinfo("Already running", "The Slint UI is already running.")
            return

        self._set_busy(True, self._btn_launch_slint)
        self._btn_stop_slint.config(state="normal")
        threading.Thread(target=self._launch_slint_worker, daemon=True).start()

    def _launch_slint_worker(self):
        log = self._launch_log

        def out(msg, tag=None):
            self._log(log, msg, tag)

        out("=== Launching AllInOnePolyglotAIJDK Slint UI ===", "ok")
        out(f"  Python : {_VENV_PY}")
        out(f"  Script : {_SLINT_PY}")
        out("")

        try:
            self._slint_proc = subprocess.Popen(
                [_VENV_PY, _SLINT_PY],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                cwd=_SCRIPT_DIR,
            )

            for line in self._slint_proc.stdout:
                tag = "err" if line.lower().startswith("error") else None
                out(line.rstrip(), tag)

            self._slint_proc.wait()
            exit_code = self._slint_proc.returncode
            tag = "ok" if exit_code == 0 else "err"
            out(f"\nSlint process exited (code {exit_code}).", tag)
        except Exception as e:
            out(f"ERROR: {e}", "err")
        finally:
            self.root.after(0, lambda: self._btn_stop_slint.config(state="disabled"))
            self._set_busy(False)

    def _do_stop_slint(self):
        if self._slint_proc and self._slint_proc.poll() is None:
            self._slint_proc.terminate()
            self._log(self._launch_log, "Slint stop requested.", "warn")
        self._btn_stop_slint.config(state="disabled")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    root = tk.Tk()
    app = ManagerApp(root)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
