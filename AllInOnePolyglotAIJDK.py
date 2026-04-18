#!/usr/bin/env python3
"""
AllInOnePolyglotAIJDK v3.3 - PySide6 Optimized for Windows
Robust dependency installation (PySide6 + requests + local wheel)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Communication paths (module overview)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  QML ↔ Python communication is handled exclusively through the `backend`
  context property injected into the QML engine via:
      engine.rootContext().setContextProperty("backend", self.backend)

  1. Chat Send
     [QML] chatInput → root.sendMessage() → backend.sendToAgent(text)
       → _chat_stack.push(_chat_snapshot())     [state saved before action]
       → query_ai(text)
           → HTTP POST  {base_url}/chat/completions
             body: {model, messages (system+history+user), temperature}
           ← JSON  {"choices":[{"message":{"content":"<reply>"}}]}
       → chatUpdated.emit(reply)
           → [QML] onChatUpdated(reply) → chatModel.append({text, isUser:false})
       → _display_history updated (mirrors chatModel for snapshot/restore)
       → undoStateChanged.emit(can_undo, can_redo)
           → [QML] canUndoChat / canRedoChat updated → button enabled state

  2. Chat Undo  (up to 20 steps — UndoRedoStack.MAX_SIZE)
     [QML] ↩ Undo button → backend.undoChatOp()
       → _chat_stack.undo()           [pop snapshot, push to _redo]
       → chat_history + _display_history restored
       → chatHistoryReset.emit(json_str)
           → [QML] onChatHistoryReset(json_str)
               → JSON.parse(json_str) → chatModel.clear() + chatModel.append(...)
       → deployLogReset.emit(deploy_log_str)
           → [QML each view] onDeployLogReset(text) → logArea.text = text
       → undoStateChanged.emit(can_undo, can_redo)

  3. Chat Redo  (up to 20 steps)
     [QML] ↪ Redo button → backend.redoChatOp()   [symmetric to undo]

  4. File Undo  (up to 20 file create/delete operations)
     [QML] ↩ File Undo button (Build Tools) → backend.undoFileOp()
       → _file_stack.undo()
       → Reverses the file operation:
           op=="create" → os.remove(path)
           op=="delete" → file re-created from saved content
       → deployLogUpdated.emit(...)

  5. File Redo  (up to 20 file create/delete operations)
     [QML] ↪ File Redo button (Build Tools) → backend.redoFileOp()   [symmetric]

  6. Environment change
     [QML] EnvironmentPills → backend.setEnvironment(env)
       → current_environment updated

  7. Planning toggle
     [QML] toggle → backend.togglePlanning(enabled)
       → is_planning_mode toggled

  8. Terminal / Shell
     [QML] → backend.runSystemCommandShell(cmd, runAsAdmin)
       → QProcess starts powershell.exe
       → readyReadStandardOutput / Error → terminalOutput.emit(...)
           → [QML] onTerminalOutput(text) → terminalArea.append(text)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import sys
import os
import subprocess
import copy
import json
import gzip
import venv
from datetime import datetime

# Resolve the script directory once, robustly, before any re-exec happens.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Wheels are stored alongside this script in the base folder.
WHEELS_DIR = _SCRIPT_DIR


def ensure_venv_and_deps():
    venv_dir = os.path.join(_SCRIPT_DIR, ".venv")
    venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    venv_pip = os.path.join(venv_dir, "Scripts", "pip.exe")

    if os.environ.get("VIRTUAL_ENV"):
        return

    try:
        import PySide6
        import requests
        import huggingface_hub
        return
    except ImportError:
        pass

    print("AllInOnePolyglotAIJDK v3.3 - First-time setup (Windows)")

    if not os.path.exists(venv_dir):
        print("Creating virtual environment...")
        venv.create(venv_dir, with_pip=True)

    # Wheels shipped with the repo (Windows x64 / pure-Python).
    # onnx-*.manylinux*.whl is Linux-only and intentionally excluded.
    LOCAL_WHEELS = [
        "setuptools-82.0.1-py3-none-any.whl",
        "huggingface_hub-0.36.2-py3-none-any.whl",
        "llama_cpp_python-0.1.66+cu121-cp311-cp311-win_amd64.whl",
        "torchvision-0.21.0-cp311-cp311-win_amd64.whl",
    ]

    print("Upgrading pip and wheel...")
    subprocess.check_call([venv_pip, "install", "--upgrade", "pip", "wheel"])

    print("Installing PySide6 and requests...")
    subprocess.check_call([venv_pip, "install", "PySide6", "requests"])

    for wheel_name in LOCAL_WHEELS:
        wheel_path = os.path.join(WHEELS_DIR, wheel_name)
        if os.path.exists(wheel_path):
            print(f"Installing local wheel: {wheel_name}")
            subprocess.check_call([venv_pip, "install", wheel_path])
        else:
            print(f"Warning: Local wheel not found: {wheel_path}")

    print("Restarting inside virtual environment...")
    os.execv(venv_python, [venv_python, os.path.abspath(__file__)] + sys.argv[1:])


ensure_venv_and_deps()

# ====================== IMPORTS ======================
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Slot, QObject, Signal, QProcess, QUrl
from PySide6.QtQml import QQmlApplicationEngine
import requests
import webbrowser


# =============================================================================
# Undo / Redo infrastructure
# =============================================================================

class UndoRedoStack:
    """
    Bounded undo/redo history stack — shared by chat-level and file-level ops.

    Capacity: MAX_SIZE = 20
      • Satisfies the ±20 file-creation/deletion requirement.
      • Satisfies the ±20 in-file correction/recall requirement.

    Behaviour
    ─────────
      push(snap)  — capture state BEFORE a mutating action.
                    Clears redo history (standard undo semantics).
                    Evicts the oldest entry (FIFO) when at capacity.
      undo()      — pop from _undo, push to _redo; returns snapshot or None.
      redo()      — pop from _redo, push to _undo; returns snapshot or None.
      can_undo    — True when _undo is non-empty.
      can_redo    — True when _redo is non-empty.

    Communication path
    ──────────────────
      Action → push(snapshot)          state captured
      ↩ Undo → undo() → snapshot       caller restores state
      ↪ Redo → redo() → snapshot       caller re-applies state
    """

    MAX_SIZE: int = 20  # ±20 as specified

    def __init__(self) -> None:
        # _undo: most-recent last (index -1 is the latest)
        self._undo: list = []
        # _redo: populated by undo(); cleared by push()
        self._redo: list = []

    # ── mutators ───────────────────────────────────────────────────────────────

    def push(self, snapshot) -> None:
        """Record state BEFORE an action so it can be restored by undo()."""
        self._undo.append(snapshot)
        if len(self._undo) > self.MAX_SIZE:
            self._undo.pop(0)   # evict oldest; stays within ±20
        self._redo.clear()      # new action invalidates redo history

    def undo(self):
        """Pop from undo stack → push to redo stack → return snapshot."""
        if not self._undo:
            return None
        snap = self._undo.pop()
        self._redo.append(snap)
        return snap

    def redo(self):
        """Pop from redo stack → push to undo stack → return snapshot."""
        if not self._redo:
            return None
        snap = self._redo.pop()
        self._undo.append(snap)
        return snap

    # ── queries ────────────────────────────────────────────────────────────────

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)


class Backend(QObject):
    # ── Signals (Python → QML) ────────────────────────────────────────────────
    # chatUpdated      : emitted after AI replies; QML appends the bubble.
    # deployLogUpdated : emitted for any log line; all three views append it.
    # terminalOutput   : emitted by QProcess stdout/stderr; BuildToolsView appends.
    # undoStateChanged : (can_undo_chat: bool, can_redo_chat: bool)
    #                    QML updates button enabled state on receipt.
    # chatHistoryReset : JSON array string of {text, isUser} — full chat list.
    #                    QML clears chatModel then re-populates from this payload.
    # deployLogReset   : full deploy-log string after an undo/redo.
    #                    Each view sets its TextArea.text = received value.
    chatUpdated = Signal(str)
    deployLogUpdated = Signal(str)
    terminalOutput = Signal(str)
    undoStateChanged = Signal(bool, bool)   # (can_undo_chat, can_redo_chat)
    chatHistoryReset = Signal(str)          # JSON array for QML chatModel reset
    deployLogReset = Signal(str)            # full log string for QML TextArea reset

    def __init__(self):
        super().__init__()
        # LM Studio endpoint — change provider / api_key for cloud models
        self.config = {
            "provider": "lmstudio",
            "api_key": "",
            "base_url": "http://localhost:1234/v1",
            "model": "local-model",
            "temperature": 0.2,
        }
        self.chat_history = []
        self.is_planning_mode = True
        self.is_devtools_enabled = False
        self.current_environment = "java"

        self.learning_library = []
        self.malicious_library = []

        self.terminal_process = None

        # _display_history: parallel list to chatModel in QML.
        # Each entry: {"text": str, "isUser": bool}
        # Required for snapshot-based undo/redo because QML ListModel is not
        # directly accessible from Python.
        self._display_history: list = []

        # _deploy_log: running deploy-log string (mirrors what QML views show).
        # Required so undo/redo can emit deployLogReset with the correct content.
        self._deploy_log: str = ""

        # ── Undo / Redo stacks ─────────────────────────────────────────────────
        # _chat_stack : snapshot per sendToAgent call (up to 20 entries)
        # _file_stack : one entry per AI-driven file create/delete op (up to 20)
        self._chat_stack = UndoRedoStack()
        self._file_stack = UndoRedoStack()

        self.current_theme = {
            "accent": "#00ff9d",
            "background": "#0a0a0a",
            "text": "#e0e0e0",
            "button": "#00ff9d",
            "frame": "#111111",
            "fontSize": 15,
            "uiFont": "Segoe UI",
            "codeFont": "Consolas",
        }

        # Core AI system prompt — prepended to every request
        self.SYSTEM_PREPEND = (
            "You are the world's best polyglot Java + GraalVM + AI engineer.\n"
            "You MUST build every project to the user's EXACT specification."
        )
        # DevTools-mode system prompt (appended when devtools are enabled)
        self.SYSTEM_PREPEND_DEVTOOLS = (
            "You are an expert Browser DevTools Controller Agent."
        )

    # ---- Library persistence ----
    # Path: Backend ↔ libraries_compressed.gz (gzip-encoded JSON on disk)

    def save_libraries(self):
        data = {"learning": self.learning_library, "malicious": self.malicious_library}
        with gzip.open("libraries_compressed.gz", "wb") as f:
            f.write(json.dumps(data).encode("utf-8"))

    def load_libraries(self):
        try:
            with gzip.open("libraries_compressed.gz", "rb") as f:
                data = json.loads(f.read().decode("utf-8"))
                self.learning_library = data.get("learning", [])
                self.malicious_library = data.get("malicious", [])
        except Exception:
            pass

    # ---- Slots ----

    # ── Snapshot helpers (used by undo/redo) ──────────────────────────────────

    def _chat_snapshot(self) -> dict:
        """
        Capture the full chat + log state before a mutating action.

        Snapshot fields
        ───────────────
          chat_history     — deep copy of self.chat_history (AI context)
          display_history  — deep copy of _display_history (QML mirror)
          deploy_log       — full deploy-log string at snapshot time

        Communication path
        ──────────────────
          _chat_snapshot() called in sendToAgent BEFORE mutating state
          → dict stored in _chat_stack._undo (up to MAX_SIZE=20 entries)
          → on undo: dict returned → _restore_chat_snapshot()
        """
        return {
            "chat_history": copy.deepcopy(self.chat_history),
            "display_history": copy.deepcopy(self._display_history),
            "deploy_log": self._deploy_log,
        }

    def _restore_chat_snapshot(self, snap: dict) -> None:
        """
        Restore chat + log state from a snapshot.

        Communication path
        ──────────────────
          _restore_chat_snapshot(snap)
            → self.chat_history restored         [AI context reverted]
            → self._display_history restored     [QML mirror reverted]
            → chatHistoryReset.emit(json_str)
                → [QML] onChatHistoryReset(json_str)
                    → JSON.parse → chatModel.clear() + chatModel.append(...)
            → self._deploy_log restored
            → deployLogReset.emit(deploy_log)
                → [QML each view] onDeployLogReset(text) → logArea.text = text
        """
        self.chat_history = copy.deepcopy(snap["chat_history"])
        self._display_history = copy.deepcopy(snap["display_history"])
        # Rebuild QML chatModel from the restored display history
        self.chatHistoryReset.emit(json.dumps(self._display_history))
        self._deploy_log = snap["deploy_log"]
        self.deployLogReset.emit(self._deploy_log)

    def _sync_undo_state(self) -> None:
        """
        Emit undoStateChanged so QML can update ↩/↪ button enabled states.

        Communication path
        ──────────────────
          _sync_undo_state()
            → undoStateChanged.emit(can_undo_chat, can_redo_chat)
                → [QML] onUndoStateChanged(canUndo, canRedo)
                    → root.canUndoChat = canUndo
                    → root.canRedoChat = canRedo
                    → ↩ / ↪ buttons' enabled binding re-evaluated
        """
        self.undoStateChanged.emit(
            self._chat_stack.can_undo,
            self._chat_stack.can_redo,
        )

    def _emit_deploy_log(self, text: str) -> None:
        """
        Append to the internal deploy log then emit deployLogUpdated.

        Communication path
        ──────────────────
          _emit_deploy_log(text)
            → self._deploy_log += "\\n" + text   [tracked for undo snapshots]
            → deployLogUpdated.emit(text)
                → [QML] onDeployLogUpdated(log)
                    → each view's TextArea.append(log)
        """
        self._deploy_log = (self._deploy_log + "\n" + text).strip()
        self.deployLogUpdated.emit(text)

    @Slot()
    def viewLibraries(self):
        # Path: [QML button] → backend.viewLibraries()
        #       → deployLogUpdated.emit(...)  → [QML] logArea.append(...)
        self.load_libraries()
        self._emit_deploy_log(
            f"JS-Learning_Library: {len(self.learning_library)} scripts\n"
            f"JS-Mal_LL: {len(self.malicious_library)} malicious scripts"
        )

    @Slot(str)
    def sendToAgent(self, text):
        """
        Send a user message to the AI and emit the reply to QML.

        Communication path
        ──────────────────
          [QML] backend.sendToAgent(text)
            → _chat_stack.push(_chat_snapshot())    [state saved, ±20 cap]
            → chat_history.append({user turn})
            → query_ai(text)                        [→ HTTP → LM Studio → reply]
            → chat_history.append({assistant turn})
            → _display_history updated
            → chatUpdated.emit(reply)
                → [QML] onChatUpdated(reply)
                    → chatModel.append({text: reply, isUser: false})
            → save_libraries()                      [→ gzip JSON → disk]
            → _sync_undo_state()                    [↩ button enabled]
        """
        if not text.strip():
            return
        # Save state BEFORE mutating so this action can be undone
        self._chat_stack.push(self._chat_snapshot())
        self.chat_history.append({"role": "user", "content": text})
        reply = self.query_ai(text)
        self.chat_history.append({"role": "assistant", "content": reply})
        # Mirror into _display_history for snapshot/restore
        self._display_history.append({"text": text, "isUser": True})
        self._display_history.append({"text": reply, "isUser": False})
        self.chatUpdated.emit(reply)
        self.save_libraries()
        self._sync_undo_state()

    # ── Chat Undo / Redo ──────────────────────────────────────────────────────

    @Slot()
    def undoChatOp(self):
        """
        Undo the last chat exchange (up to 20 steps back).

        Communication path
        ──────────────────
          [QML ↩ button] → backend.undoChatOp()
            → _chat_stack.undo()              [pop _undo, push to _redo]
            → _restore_chat_snapshot(snap)
                → chatHistoryReset.emit(json_str)   [QML rebuilds chatModel]
                → deployLogReset.emit(deploy_log)   [QML resets log TextAreas]
            → _emit_deploy_log("[undo] ...")
            → _sync_undo_state()                    [↩/↪ buttons refreshed]
        """
        snap = self._chat_stack.undo()
        if snap is None:
            return
        self._restore_chat_snapshot(snap)
        self._emit_deploy_log("[undo] Chat state restored")
        self._sync_undo_state()

    @Slot()
    def redoChatOp(self):
        """
        Redo a previously undone chat exchange (up to 20 steps forward).

        Communication path
        ──────────────────
          [QML ↪ button] → backend.redoChatOp()
            → _chat_stack.redo()              [pop _redo, push back to _undo]
            → _restore_chat_snapshot(snap)
                → chatHistoryReset.emit(json_str)
                → deployLogReset.emit(deploy_log)
            → _emit_deploy_log("[redo] ...")
            → _sync_undo_state()
        """
        snap = self._chat_stack.redo()
        if snap is None:
            return
        self._restore_chat_snapshot(snap)
        self._emit_deploy_log("[redo] Chat state re-applied")
        self._sync_undo_state()

    # ── File-level Undo / Redo (up to 20 file create/delete operations) ───────

    @Slot()
    def undoFileOp(self):
        """
        Undo the last file-level operation (create or delete), up to 20 steps.

        File operations are pushed onto _file_stack by methods that create or
        delete files (e.g. createProjectWithBuildSystem).  Each entry is a dict:
            {"op": "create"|"delete", "path": str, "content": bytes|None}

        Communication path
        ──────────────────
          [QML ↩ File Undo button] → backend.undoFileOp()
            → _file_stack.undo()          [pop most-recent file op]
            → "create" op → os.remove(path)   [file deleted]
            → "delete" op → file re-created from saved content
            → deployLogUpdated.emit(...)  [QML log updated]
        """
        snap = self._file_stack.undo()
        if snap is None:
            self._emit_deploy_log("[file undo] Nothing to undo")
            return
        op, path, content = snap.get("op"), snap.get("path"), snap.get("content")
        try:
            if op == "create":
                # Undo a create → delete the file
                if os.path.exists(path):
                    os.remove(path)
                    self._emit_deploy_log(f"[file undo] Deleted: {path}")
                else:
                    self._emit_deploy_log(f"[file undo] Already absent: {path}")
            elif op == "delete":
                # Undo a delete → re-create the file
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(content or b"")
                self._emit_deploy_log(f"[file undo] Restored: {path}")
            else:
                self._emit_deploy_log(f"[file undo] Unknown op: {op}")
        except Exception as exc:
            self._emit_deploy_log(f"[file undo] Error: {exc}")

    @Slot()
    def redoFileOp(self):
        """
        Redo a previously undone file-level operation, up to 20 steps forward.

        Communication path
        ──────────────────
          [QML ↪ File Redo button] → backend.redoFileOp()
            → _file_stack.redo()          [pop from _redo]
            → "create" op → file re-created (content was stored at push time)
            → "delete" op → os.remove(path)
            → deployLogUpdated.emit(...)
        """
        snap = self._file_stack.redo()
        if snap is None:
            self._emit_deploy_log("[file redo] Nothing to redo")
            return
        op, path, content = snap.get("op"), snap.get("path"), snap.get("content")
        try:
            if op == "create":
                # Redo a create → recreate the file
                os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                with open(path, "wb") as fh:
                    fh.write(content or b"")
                self._emit_deploy_log(f"[file redo] Recreated: {path}")
            elif op == "delete":
                # Redo a delete → delete again
                if os.path.exists(path):
                    os.remove(path)
                    self._emit_deploy_log(f"[file redo] Deleted: {path}")
                else:
                    self._emit_deploy_log(f"[file redo] Already absent: {path}")
            else:
                self._emit_deploy_log(f"[file redo] Unknown op: {op}")
        except Exception as exc:
            self._emit_deploy_log(f"[file redo] Error: {exc}")

    @Slot(str)
    def setEnvironment(self, env):
        # Path: [QML ComboBox / pill] → backend.setEnvironment(env)
        self.current_environment = env

    @Slot(bool)
    def togglePlanning(self, enabled):
        # Path: [QML toggle] → backend.togglePlanning(enabled)
        #       → is_planning_mode toggled (controls AI system message injection)
        self.is_planning_mode = enabled

    @Slot(bool)
    def toggleDevTools(self, enabled):
        # Path: [QML toggle] → backend.toggleDevTools(enabled)
        #       → is_devtools_enabled toggled
        #       → deployLogUpdated.emit  → [QML] log appended
        self.is_devtools_enabled = enabled
        self._emit_deploy_log(
            f"DevTools Integration {'ENABLED' if enabled else 'DISABLED'}"
        )

    @Slot()
    def recreateAndSecurityScan(self):
        # Path: [QML button] → backend.recreateAndSecurityScan()
        #       → sendToAgent(predefined prompt)  [→ AI → chatUpdated]
        if not self.is_devtools_enabled:
            self._emit_deploy_log("DevTools must be enabled first.")
            return
        self._emit_deploy_log("Recreating page and running security scan...")
        self.sendToAgent(
            "Recreate the current webpage, sandbox it, and run JavaScript to check "
            "for malicious scripts and explore configurations."
        )

    @Slot(str)
    def sendDevToolsCommand(self, command):
        # Path: [QML TextField + button] → backend.sendDevToolsCommand(cmd)
        #       → deployLogUpdated.emit  → [QML] logArea.append
        if not self.is_devtools_enabled:
            self._emit_deploy_log("DevTools not enabled.")
            return
        self._emit_deploy_log(f"Executing: {command}")

    @Slot()
    def openJavaToolkitDownload(self):
        # Path: [QML button] → backend.openJavaToolkitDownload()
        #       → webbrowser.open(url)    [system default browser launched]
        #       → deployLogUpdated.emit
        webbrowser.open("https://adoptium.net/temurin/releases/")
        self._emit_deploy_log("Opened Java Development Toolkit download page")

    @Slot()
    def checkJavaToolkit(self):
        # Path: [QML button] → backend.checkJavaToolkit()
        #       → subprocess.run(["java", "-version"])
        #       → deployLogUpdated.emit(output)
        try:
            result = subprocess.run(
                ["java", "-version"], capture_output=True, text=True, shell=True
            )
            self._emit_deploy_log(
                f"Java Development Toolkit detected:\n{result.stderr.strip()}"
            )
        except Exception:
            self._emit_deploy_log("Java Development Toolkit not found.")

    @Slot(str)
    def createProjectWithBuildSystem(self, system_type):
        """
        Ask the AI to scaffold a project and record the op in _file_stack.

        Communication path
        ──────────────────
          [QML button] → backend.createProjectWithBuildSystem(type)
            → _file_stack.push({"op":"create","path":project_dir,"content":None})
                [records that this dir was created so undoFileOp can delete it]
            → sendToAgent(predefined prompt)   [→ AI → chatUpdated]
        """
        # Record the file-level create operation for undo/redo (±20 cap)
        project_dir = os.path.join(_SCRIPT_DIR, "generated_project")
        self._file_stack.push({"op": "create", "path": project_dir, "content": None})
        if system_type == "xml":
            self.sendToAgent(
                "Create a complete project using XML-based build configuration "
                "with GraalVM support."
            )
        else:
            self.sendToAgent(
                "Create a complete project using script-based build configuration "
                "with GraalVM support."
            )

    @Slot()
    def checkGit(self):
        # Path: [QML button] → backend.checkGit()
        #       → subprocess.run(["git","--version"])  → deployLogUpdated.emit
        try:
            result = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, shell=True
            )
            self._emit_deploy_log(f"Git detected: {result.stdout.strip()}")
        except Exception:
            self._emit_deploy_log("Git not found.")

    @Slot()
    def openGitDownload(self):
        # Path: [QML button] → backend.openGitDownload()
        #       → webbrowser.open(url)  → deployLogUpdated.emit
        webbrowser.open("https://git-scm.com/download/win")
        self._emit_deploy_log("Opened Git for Windows download page.")

    @Slot(str)
    def runGitCommand(self, command):
        # Path: [QML button] → backend.runGitCommand(cmd)
        #       → subprocess.run("git " + cmd, shell=True)
        #       → deployLogUpdated.emit(output)
        self._emit_deploy_log(f"Running: git {command}")
        try:
            result = subprocess.run(
                f"git {command}", capture_output=True, text=True, shell=True
            )
            output = result.stdout.strip() if result.stdout else result.stderr.strip()
            self._emit_deploy_log(output)
        except Exception as e:
            self._emit_deploy_log(f"Git error: {e}")

    @Slot(str, bool)
    def runSystemCommandShell(self, command, runAsAdmin):
        # Path: [QML button] → backend.runSystemCommandShell(cmd, admin)
        #       → QProcess.start("powershell.exe", ...)
        #       → readyReadStandardOutput / Error
        #           → terminalReadyRead()
        #               → terminalOutput.emit(text)
        #                   → [QML] onTerminalOutput(text)
        #                       → terminalArea.append(text)
        if self.terminal_process and self.terminal_process.state() == QProcess.Running:
            self._emit_deploy_log("Stopping previous process...")
            self.terminal_process.terminate()
            if not self.terminal_process.waitForFinished(3000):
                self.terminal_process.kill()

        self.terminal_process = QProcess()
        self.terminal_process.readyReadStandardOutput.connect(self.terminalReadyRead)
        self.terminal_process.readyReadStandardError.connect(self.terminalReadyRead)

        if runAsAdmin:
            self.terminal_process.start(
                "powershell.exe",
                [
                    "-Command",
                    f"Start-Process powershell -Verb RunAs "
                    f"-ArgumentList '-NoExit -Command {command}'",
                ],
            )
        else:
            self.terminal_process.start("powershell.exe", ["-Command", command])

    def terminalReadyRead(self):
        output = (
            self.terminal_process.readAllStandardOutput()
            .data()
            .decode("utf-8", errors="ignore")
        )
        error = (
            self.terminal_process.readAllStandardError()
            .data()
            .decode("utf-8", errors="ignore")
        )
        if output:
            self.terminalOutput.emit(output.strip())
        if error:
            self.terminalOutput.emit("ERROR: " + error.strip())

    # ---- Theme slots ----
    # Path for all theme slots:
    #   [QML SettingsView] → backend.updateTheme*/save/load/reset()
    #   → current_theme dict updated
    #   → deployLogUpdated.emit  → [QML] themeLogArea.append

    @Slot(str, str)
    def updateThemeColor(self, key, color):
        self.current_theme[key] = color

    @Slot(int)
    def updateFontSize(self, size):
        self.current_theme["fontSize"] = size

    @Slot(str)
    def updateUIFont(self, font):
        self.current_theme["uiFont"] = font

    @Slot(str)
    def updateCodeFont(self, font):
        self.current_theme["codeFont"] = font

    @Slot()
    def saveThemeLayout(self):
        # Path: → json.dump → theme_layout.json → deployLogUpdated.emit
        try:
            with open("theme_layout.json", "w") as f:
                json.dump(self.current_theme, f, indent=4)
            self._emit_deploy_log("Theme layout saved to theme_layout.json")
        except Exception as e:
            self._emit_deploy_log(f"Failed to save theme: {e}")

    @Slot()
    def loadThemeLayout(self):
        # Path: → json.load ← theme_layout.json → current_theme updated
        try:
            with open("theme_layout.json", "r") as f:
                self.current_theme = json.load(f)
            self._emit_deploy_log("Theme layout loaded successfully")
        except Exception:
            self._emit_deploy_log("No saved theme found.")

    @Slot()
    def resetTheme(self):
        self.current_theme = {
            "accent": "#00ff9d",
            "background": "#0a0a0a",
            "text": "#e0e0e0",
            "button": "#00ff9d",
            "frame": "#111111",
            "fontSize": 15,
            "uiFont": "Segoe UI",
            "codeFont": "Consolas",
        }
        self._emit_deploy_log("Theme reset to default")

    # ---- AI query ----

    def query_ai(self, user_message):
        messages = [{"role": "system", "content": self.SYSTEM_PREPEND}]
        if self.is_devtools_enabled:
            messages.append({"role": "system", "content": self.SYSTEM_PREPEND_DEVTOOLS})
        if self.is_planning_mode:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "PLANNING MODE ENABLED: First output a detailed PLAN "
                        "and ask for confirmation."
                    ),
                }
            )
        messages.extend(self.chat_history)
        messages.append({"role": "user", "content": user_message})

        try:
            url = f"{self.config['base_url']}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.config["provider"] != "lmstudio":
                headers["Authorization"] = f"Bearer {self.config['api_key']}"
            payload = {
                "model": self.config["model"],
                "messages": messages,
                "temperature": self.config["temperature"],
                "stream": False,
            }
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"AI Error: {str(e)}"


class MainWindow:
    """Owns the QQmlApplicationEngine and the Backend, keeping them alive."""

    def __init__(self):
        self.backend = Backend()
        self.backend.load_libraries()

        self.engine = QQmlApplicationEngine()
        self.engine.rootContext().setContextProperty("backend", self.backend)

        qml_path = os.path.join(_SCRIPT_DIR, "qml", "main.qml")
        self.engine.load(QUrl.fromLocalFile(qml_path))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("AllInOnePolyglotAIJDK")
    main = MainWindow()
    if not main.engine.rootObjects():
        sys.exit(1)
    sys.exit(app.exec())
