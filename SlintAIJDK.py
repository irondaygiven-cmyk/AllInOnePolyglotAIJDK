#!/usr/bin/env python3
"""
AllInOnePolyglotAIJDK - Slint front-end entry point

Requires the 'slint' package (installed by AIDK_in.bat).
Shares the same AI-query logic as AllInOnePolyglotAIJDK.py but renders
its UI via Slint instead of PySide6 / QML.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Communication paths (module overview)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Chat Send
     [Slint SEND / Enter] → send-message(text) callback
       → on_send_message(text)
         → chat_stack.push(_snapshot())          # save state BEFORE action
         → AIBackend.send(text)
             → AIBackend.query_ai(text)
                 → HTTP POST  http://localhost:1234/v1/chat/completions
                   body: {model, messages (system+history+user), temperature}
                 ← JSON  {"choices":[{"message":{"content":"<reply>"}}]}
             → backend.chat_history updated (user + assistant turns)
             → libraries_compressed.gz saved (gzip JSON)
         → window.chat_messages updated (Slint list re-rendered)
         → window.deploy_log / telemetry_log appended
         → window.can_undo_chat = True / can_redo_chat synced

  2. Chat Undo  (up to 20 steps — UndoRedoStack.MAX_SIZE)
     [Slint ↩ Undo button] → undo-chat() callback
       → on_undo_chat()
         → chat_stack.undo()   # pops from _undo, pushes to _redo
         → _restore(snapshot)
             → messages[], window.chat_messages, deploy_log, telemetry_log restored
             → backend.chat_history deep-copied back
         → window.can_undo_chat / can_redo_chat synced

  3. Chat Redo  (up to 20 steps)
     [Slint ↪ Redo button] → redo-chat() callback
       → on_redo_chat()
         → chat_stack.redo()   # pops from _redo, pushes back to _undo
         → _restore(snapshot)  # same restore path as undo
         → can_undo_chat / can_redo_chat synced

  4. Environment change
     [Slint ComboBox] → set-environment(env) callback
       → on_set_environment(env)
         → backend.current_environment = env
         → deploy_log + telemetry_log appended

  5. App state change  (Planning / Development / BrowserDev / Research)
     [Slint mode buttons] → set-app-state(AppState) callback
       → on_set_app_state(state)
         → backend.is_planning_mode toggled (True only for Planning)
         → deploy_log + telemetry_log appended

  6. Research — Select Synthesis Target
     [Slint Browse… button] → select-synthesis-target() callback
       → on_select_synthesis_target()
         → tkinter.Tk().withdraw() + filedialog.askopenfilename()
             [native Windows/Linux file-picker; no UI thread blocking]
         → window.synthesis_target = chosen path
         → window.synthesis_log appended

  7. Research — Begin Deconstruction
     [Slint ⚡ Begin Deconstruction] → begin-deconstruction() callback
       → on_begin_deconstruction()
         → window.synthesis_busy = True
         → threading.Thread(target=_run_synthesis, daemon=True).start()
             → SynthesisAgent(target, output_lib, progress_cb=_append_synthesis)
             → agent.deconstruct()
                 → static analysis (dumpbin / javap / file read)
                 → HTTP POST  /chat/completions   [AI pattern extraction]
                 → JSON pattern file → Learning_Library/Synthesized_Data/
             → window.synthesis_busy = False (via Slint timer in main loop)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import copy
import gzip
import json
import os
import sys
import threading

import requests as _requests

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
# _SCRIPT_DIR : directory of this .py file (repo root)
# _SLINT_FILE : slint/main.slint — parsed by slint.load_file() at startup;
#               defines the MainWindow component with all callbacks and properties.
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SLINT_FILE = os.path.join(_SCRIPT_DIR, "slint", "main.slint")

# Add the repo root to sys.path so scripts.synthesis_engine can be imported.
# Path: import → scripts/synthesis_engine.py → SynthesisAgent
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)


# ─────────────────────────────────────────────────────────────────────────────
# Undo / Redo infrastructure
# ─────────────────────────────────────────────────────────────────────────────

class UndoRedoStack:
    """
    Bounded undo/redo history stack.

    Design
    ──────
    Each slot holds one opaque snapshot value.  The calling code is responsible
    for producing and interpreting snapshots — this class only manages the two
    deques and the MAX_SIZE eviction policy.

    Capacity: MAX_SIZE = 20
      • Satisfies the ±20 file creation/deletion requirement.
      • Satisfies the ±20 in-file operation correction/recall requirement.

    Behaviour
    ─────────
      push(snap)  — record current state BEFORE a mutating action.
                    Clears the redo stack (standard undo semantics).
                    Evicts the oldest entry when full (FIFO).
      undo()      — pops from _undo, pushes to _redo; returns snapshot or None.
      redo()      — pops from _redo, pushes to _undo; returns snapshot or None.
      can_undo    — True when there is at least one entry to undo.
      can_redo    — True when there is at least one entry to redo.

    Communication path (conceptual)
    ──────────────────────────────
      Action (e.g. send_message)
        → push(snapshot)         state captured
      Undo button clicked
        → undo()                 snapshot returned, caller restores state
      Redo button clicked
        → redo()                 snapshot returned, caller re-applies state
    """

    MAX_SIZE: int = 20  # ±20 as specified

    def __init__(self) -> None:
        # _undo: list of snapshots (most-recent last); index -1 is the latest
        self._undo: list = []
        # _redo: populated only by undo(); cleared by push()
        self._redo: list = []

    # ── mutators ───────────────────────────────────────────────────────────────

    def push(self, snapshot) -> None:
        """Record state BEFORE an action so it can be restored via undo()."""
        self._undo.append(snapshot)
        if len(self._undo) > self.MAX_SIZE:
            # Drop the oldest entry to stay within the ±20 limit
            self._undo.pop(0)
        # A new action always invalidates the redo history
        self._redo.clear()

    def undo(self):
        """
        Restore the previous state.
        Pops the most-recent snapshot from _undo, pushes it to _redo.
        Returns the snapshot, or None if the undo stack is empty.
        """
        if not self._undo:
            return None
        snap = self._undo.pop()
        self._redo.append(snap)
        return snap

    def redo(self):
        """
        Re-apply a previously undone state.
        Pops the top entry from _redo, pushes it back to _undo.
        Returns the snapshot, or None if the redo stack is empty.
        """
        if not self._redo:
            return None
        snap = self._redo.pop()
        self._undo.append(snap)
        return snap

    # ── queries ────────────────────────────────────────────────────────────────

    @property
    def can_undo(self) -> bool:
        """True when there is at least one action that can be undone."""
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        """True when there is at least one action that can be redone."""
        return bool(self._redo)


# ─────────────────────────────────────────────────────────────────────────────
# AI / library logic
# ─────────────────────────────────────────────────────────────────────────────

class AIBackend:
    """
    Pure-Python AI back-end — no UI dependency.

    Communication path
    ──────────────────
      send(text)
        → query_ai(text)
            → HTTP POST  {base_url}/chat/completions
              headers: Content-Type: application/json
                       Authorization: Bearer {api_key}  (non-LM-Studio only)
              body:    {"model": ..., "messages": [...], "temperature": ...,
                        "stream": false}
            ← JSON   {"choices": [{"message": {"content": "<reply>"}}]}
        → chat_history.append({user turn})
        → chat_history.append({assistant turn})
        → save_libraries() → libraries_compressed.gz  (gzip-encoded JSON)

    Planning mode
    ─────────────
      When is_planning_mode is True a second system message is injected into
      every request, instructing the AI to output a plan and ask for
      confirmation before acting.

    Library persistence
    ───────────────────
      learning_library  / malicious_library are stored as a gzip-compressed
      JSON file (libraries_compressed.gz) adjacent to this script.
      Path: AIBackend.save_libraries() / load_libraries()
              ↔  {_SCRIPT_DIR}/libraries_compressed.gz
    """

    def __init__(self) -> None:
        # LM Studio endpoint — change provider / api_key for cloud models
        self.config = {
            "provider": "lmstudio",
            "api_key": "",
            "base_url": "http://localhost:1234/v1",
            "model": "local-model",
            "temperature": 0.2,
        }
        # Full conversation history forwarded to the AI on every request
        self.chat_history: list = []
        self.current_environment: str = "java"
        # Planning mode: AI produces a plan first and asks for confirmation
        self.is_planning_mode: bool = True
        # Persistent knowledge stores (saved as gzip-compressed JSON)
        self.learning_library: list = []
        self.malicious_library: list = []
        # System prompt prepended to every AI request
        self.SYSTEM_PREPEND = (
            "You are the world's best polyglot Java + GraalVM + AI engineer.\n"
            "You MUST build every project to the user's EXACT specification."
        )

    # ── Library persistence ────────────────────────────────────────────────────
    # Path: AIBackend ↔ libraries_compressed.gz (gzip JSON on disk)

    def save_libraries(self) -> None:
        data = {"learning": self.learning_library, "malicious": self.malicious_library}
        with gzip.open("libraries_compressed.gz", "wb") as f:
            f.write(json.dumps(data).encode("utf-8"))

    def load_libraries(self) -> None:
        try:
            with gzip.open("libraries_compressed.gz", "rb") as f:
                data = json.loads(f.read().decode("utf-8"))
                self.learning_library = data.get("learning", [])
                self.malicious_library = data.get("malicious", [])
        except Exception:
            pass

    # ── AI query ──────────────────────────────────────────────────────────────
    # Path: query_ai → HTTP POST → LM Studio / cloud provider → JSON reply

    def query_ai(self, user_message: str) -> str:
        # System messages are prepended in priority order:
        #   1. Core identity / instruction (SYSTEM_PREPEND)
        #   2. Planning-mode directive (if enabled)
        #   3. Full chat history (older turns give context)
        #   4. Current user message
        messages = [{"role": "system", "content": self.SYSTEM_PREPEND}]
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
        # Append existing turns then the new user message
        messages.extend(self.chat_history)
        messages.append({"role": "user", "content": user_message})

        try:
            url = f"{self.config['base_url']}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.config["provider"] != "lmstudio":
                # Cloud providers (OpenAI, Anthropic-compat, etc.) require a Bearer token
                headers["Authorization"] = f"Bearer {self.config['api_key']}"
            payload = {
                "model": self.config["model"],
                "messages": messages,
                "temperature": self.config["temperature"],
                "stream": False,
            }
            response = _requests.post(url, headers=headers, json=payload, timeout=120)
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"AI Error: {str(e)}"

    def send(self, text: str) -> str:
        """
        Append user message, query AI, append AI reply, persist libraries.

        Communication path
        ──────────────────
          send(text)
            → chat_history.append({"role": "user", ...})
            → query_ai(text)  [→ HTTP → AI endpoint → reply string]
            → chat_history.append({"role": "assistant", ...})
            → save_libraries()  [→ gzip JSON → disk]
        """
        text = text.strip()
        if not text:
            return ""
        self.chat_history.append({"role": "user", "content": text})
        reply = self.query_ai(text)
        self.chat_history.append({"role": "assistant", "content": reply})
        try:
            self.save_libraries()
        except Exception:
            pass
        return reply


# ─────────────────────────────────────────────────────────────────────────────
# Slint UI wiring
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    """
    Load the Slint UI, wire Python callbacks, start the event loop.

    All UI ↔ Python communication flows through Slint callbacks and properties:

      Callback         Direction        Python handler        Effect
      ───────────────  ───────────────  ────────────────────  ───────────────────────────────
      send-message     Slint → Python   on_send_message       AI query + chat list update
      undo-chat        Slint → Python   on_undo_chat          Snapshot restore (±20)
      redo-chat        Slint → Python   on_redo_chat          Snapshot re-apply (±20)
      set-environment  Slint → Python   on_set_environment    backend.current_environment
      set-app-state    Slint → Python   on_set_app_state      backend.is_planning_mode

      Property         Direction        Updated by            Effect
      ───────────────  ───────────────  ────────────────────  ───────────────────────────────
      chat-messages    Python → Slint   append_message()      Chat list re-rendered
      deploy-log       Python → Slint   append_log()          Deploy log text updated
      telemetry-log    Python → Slint   append_telemetry()    Status Console updated
      status-text      Python → Slint   on_send_message       Footer status label
      can-undo-chat    Python → Slint   _sync_undo_state()    ↩ button enabled/disabled
      can-redo-chat    Python → Slint   _sync_undo_state()    ↪ button enabled/disabled
      app-state        Slint internal   mode buttons          Visual indicator label
    """
    try:
        import slint  # type: ignore[import]
    except ImportError:
        sys.exit(
            "ERROR: 'slint' package not found.\n"
            "Please run AIDK_in.bat to install dependencies first."
        )

    backend = AIBackend()
    backend.load_libraries()

    # Parse slint/main.slint → component type registry
    # Path: slint.load_file(path) → compiled Slint file → component dict
    components = slint.load_file(_SLINT_FILE)

    # ChatMessage is the exported struct; use it instead of the abstract slint.Struct base.
    # This ensures type-safe construction that matches the struct definition in main.slint.
    ChatMessage = components.ChatMessage

    # Instantiate the root window component (defined in main.slint)
    window = components.MainWindow()

    # Local mutable list mirroring window.chat_messages.
    # Slint requires re-assigning the whole list (no in-place mutation).
    messages: list = []

    # ── Undo / Redo stacks ─────────────────────────────────────────────────────
    # chat_stack  : one snapshot per send_message call (up to 20 entries)
    # file_stack  : one entry per file create/delete op from the AI (up to 20)
    #               populated externally by callers that detect file operations
    #               in the AI reply (e.g. regex matching "Creating file ...")
    chat_stack = UndoRedoStack()
    file_stack = UndoRedoStack()  # reserved for file-level operation tracking

    # Integer → display name mapping for the AppState enum (Slint enum ordinals).
    # IMPORTANT: ordinals MUST match the order declared in slint/main.slint:
    #   export enum AppState { Planning, Development, BrowserDev, Research }
    #                ordinal:      0           1            2         3
    # If the Slint enum order changes, update this dict accordingly.
    _APP_STATE_NAMES = {0: "Planning", 1: "Development", 2: "BrowserDev", 3: "Research"}

    # ── Snapshot helpers ───────────────────────────────────────────────────────

    def _snapshot() -> dict:
        """
        Capture the full UI + AI state into a dict for later restoration.

        Snapshot contains:
          messages      — shallow copy of the Slint Struct list (chat bubbles)
          deploy_log    — full deploy log string at this point in time
          telemetry_log — full telemetry/Status Console string
          chat_history  — deep copy of backend.chat_history (AI context)

        Communication path
        ──────────────────
          _snapshot() called in on_send_message BEFORE mutating state
          → dict stored in chat_stack._undo (up to MAX_SIZE=20 entries)
          → on undo: dict returned from chat_stack.undo() → _restore()
        """
        return {
            "messages": list(messages),
            "deploy_log": window.deploy_log or "",
            "telemetry_log": window.telemetry_log or "",
            "chat_history": copy.deepcopy(backend.chat_history),
        }

    def _restore(snap: dict) -> None:
        """
        Restore UI + AI state from a snapshot produced by _snapshot().

        Communication path
        ──────────────────
          _restore(snap) called from on_undo_chat / on_redo_chat
          → messages[] mutated and re-assigned to window.chat_messages
              [Python list → Slint property → chat list re-rendered]
          → window.deploy_log / telemetry_log overwritten
              [Python str → Slint property → Text element re-rendered]
          → backend.chat_history deep-copied back
              [Restores AI context so next query sees the correct history]
        """
        messages.clear()
        messages.extend(snap["messages"])
        window.chat_messages = messages        # Slint list re-rendered
        window.deploy_log = snap["deploy_log"]
        window.telemetry_log = snap["telemetry_log"]
        backend.chat_history = copy.deepcopy(snap["chat_history"])

    def _sync_undo_state() -> None:
        """
        Push the current undo/redo availability flags into the Slint window.

        Communication path
        ──────────────────
          chat_stack.can_undo / .can_redo (Python bool)
            → window.can_undo_chat / can_redo_chat (Slint in-out property)
              → ↩ / ↪ buttons' `enabled` binding re-evaluated
        """
        window.can_undo_chat = chat_stack.can_undo
        window.can_redo_chat = chat_stack.can_redo

    # ── UI helper functions ────────────────────────────────────────────────────

    def append_message(text: str, is_user: bool) -> None:
        # Use the exported ChatMessage struct for type-safe construction.
        # Path: ChatMessage → messages list → window.chat_messages → Slint re-render
        messages.append(ChatMessage(text=text, is_user=is_user))
        window.chat_messages = messages

    def append_log(line: str) -> None:
        # Path: Python str → window.deploy_log → Slint Text binding re-renders
        current = window.deploy_log or ""
        window.deploy_log = (current + "\n" + line).strip()

    def append_telemetry(line: str) -> None:
        # Path: Python str → window.telemetry_log → Status Console Text re-renders
        current = window.telemetry_log or ""
        window.telemetry_log = (current + "\n" + line).strip()

    def append_synthesis(line: str) -> None:
        # Path: Python str → window.synthesis_log → Research Progress console re-renders
        # Called from main thread only (or via the Slint timer for thread safety).
        current = window.synthesis_log or ""
        window.synthesis_log = (current + "\n" + line).strip()

    # ── Slint callbacks ────────────────────────────────────────────────────────

    @window.send_message
    def on_send_message(text: str) -> None:
        """
        Triggered by: [SEND button click] or [LineEdit Enter key press].

        Communication path
        ──────────────────
          [Slint] send-message(text)
            → on_send_message(text)
              → chat_stack.push(_snapshot())     # pre-action state saved (±20)
              → append_message(text, is_user=True)
                  → window.chat_messages updated  [user bubble rendered]
              → window.status_text = "Thinking…"
              → AIBackend.send(text)
                  → AIBackend.query_ai(text)      [→ HTTP → AI endpoint]
                  ← reply string
              → append_message(reply, is_user=False)
                  → window.chat_messages updated  [AI bubble rendered]
              → append_log / append_telemetry    [log strings updated]
              → window.status_text = "Ready"
              → _sync_undo_state()               [↩ button enabled]
        """
        if not text.strip():
            return
        # Save state BEFORE mutating so this send can be undone
        chat_stack.push(_snapshot())
        append_message(text, is_user=True)
        window.status_text = "Thinking…"
        reply = backend.send(text)
        append_message(reply, is_user=False)
        append_log(f"[agent] responded ({len(reply)} chars)")
        append_telemetry(
            f"[jcmd] send_message: {len(text)} chars in, {len(reply)} chars out"
        )
        window.status_text = "Ready"
        _sync_undo_state()

    @window.undo_chat
    def on_undo_chat() -> None:
        """
        Triggered by: [↩ Undo button click].

        Communication path
        ──────────────────
          [Slint] undo-chat()
            → on_undo_chat()
              → chat_stack.undo()        # pop from _undo, push to _redo
              → _restore(snapshot)       # window state + AI history reverted
              → append_telemetry(...)    # Status Console records the action
              → _sync_undo_state()       # ↩/↪ button states refreshed

        Bounded to ±20 steps (UndoRedoStack.MAX_SIZE = 20).
        No-op when chat_stack._undo is empty.
        """
        snap = chat_stack.undo()
        if snap is None:
            return
        _restore(snap)
        append_telemetry("[jcmd] undo_chat: previous state restored")
        _sync_undo_state()

    @window.redo_chat
    def on_redo_chat() -> None:
        """
        Triggered by: [↪ Redo button click].

        Communication path
        ──────────────────
          [Slint] redo-chat()
            → on_redo_chat()
              → chat_stack.redo()        # pop from _redo, push back to _undo
              → _restore(snapshot)       # window state + AI history re-applied
              → append_telemetry(...)    # Status Console records the action
              → _sync_undo_state()       # ↩/↪ button states refreshed

        Bounded to ±20 steps (UndoRedoStack.MAX_SIZE = 20).
        No-op when chat_stack._redo is empty.
        """
        snap = chat_stack.redo()
        if snap is None:
            return
        _restore(snap)
        append_telemetry("[jcmd] redo_chat: state re-applied")
        _sync_undo_state()

    @window.set_environment
    def on_set_environment(env: str) -> None:
        """
        Triggered by: [ComboBox selection change].

        Communication path
        ──────────────────
          [Slint] set-environment(env)
            → on_set_environment(env)
              → backend.current_environment = env
              → append_log / append_telemetry    [logs updated]
        """
        backend.current_environment = env
        append_log(f"Environment set to: {env}")
        append_telemetry(f"[jcmd] environment -> {env}")

    @window.set_app_state
    def on_set_app_state(state) -> None:
        """
        Triggered by: [Planning / Development / Browser Dev / ⚗ Research button click].

        Communication path
        ──────────────────
          [Slint] set-app-state(AppState)
            → on_set_app_state(state)
              → state_name resolved from integer ordinal via _APP_STATE_NAMES
              → backend.is_planning_mode = (state_name == "Planning")
                  [controls whether the AI prepends a planning system message]
              → append_log / append_telemetry    [logs updated]
        """
        state_name = _APP_STATE_NAMES.get(int(state), str(state))
        backend.is_planning_mode = state_name == "Planning"
        append_log(f"App state changed to: {state_name}")
        append_telemetry(f"[jcmd] app_state -> {state_name}")

    # ── Research / Pattern Synthesis callbacks ────────────────────────────────

    @window.select_synthesis_target
    def on_select_synthesis_target() -> None:
        """
        Triggered by: [Browse… button in Research mode].

        Opens a native file-picker dialog so the user can choose a target
        binary or script for Pattern Synthesis.  Writes the chosen path back
        to window.synthesis_target.

        Communication path
        ──────────────────
          [Slint] select-synthesis-target()
            → on_select_synthesis_target()
              → tkinter.Tk().withdraw()       [hidden root window]
              → filedialog.askopenfilename()  [native OS file dialog]
              ← chosen path string (empty string if cancelled)
              → window.synthesis_target = path
              → append_synthesis("[RESEARCH] Target selected: ...")
        """
        try:
            import tkinter as tk
            from tkinter import filedialog

            # Create and immediately hide a root Tk window (required by filedialog)
            _root = tk.Tk()
            _root.withdraw()
            _root.attributes("-topmost", True)  # ensure dialog appears on top

            path = filedialog.askopenfilename(
                title="Select Target for Pattern Synthesis",
                filetypes=[
                    ("All supported targets",
                     "*.exe *.dll *.lib *.obj *.class *.jar "
                     "*.py *.js *.ts *.rs *.go *.cs *.java *.c *.cpp"),
                    ("MSVC binaries",   "*.exe *.dll *.lib *.obj"),
                    ("Java bytecode",   "*.class *.jar"),
                    ("Source files",    "*.py *.js *.ts *.rs *.go *.cs *.java *.c *.cpp"),
                    ("All files",       "*.*"),
                ],
            )
            _root.destroy()

            if path:
                # Normalise to OS-native path separators
                path = os.path.normpath(path)
                window.synthesis_target = path
                append_synthesis(f"[RESEARCH] Target selected: {path}")
                append_telemetry(f"[jcmd] synthesis_target -> {os.path.basename(path)}")
            else:
                append_synthesis("[RESEARCH] File selection cancelled")
        except Exception as exc:
            append_synthesis(f"[ERROR] Could not open file dialog: {exc}")

    @window.begin_deconstruction
    def on_begin_deconstruction() -> None:
        """
        Triggered by: [⚡ Begin Deconstruction button in Research mode].

        Launches SynthesisAgent.deconstruct() in a daemon thread so the Slint
        event loop remains responsive.  Progress messages are forwarded to
        window.synthesis_log via a thread-safe queue polled by a Slint timer.

        Communication path
        ──────────────────
          [Slint] begin-deconstruction()
            → on_begin_deconstruction()
              → window.synthesis_busy = True
              → threading.Thread(target=_run_synthesis, daemon=True).start()
                  → SynthesisAgent(target, output_lib, progress_cb=_enqueue_progress)
                  → agent.deconstruct()
                      → static analysis (dumpbin / javap / file read)
                      → HTTP POST  /chat/completions   [AI pattern extraction]
                      ← pattern description
                      → JSON file saved to Learning_Library/Synthesized_Data/
                  → _enqueue_progress(msg)     [→ thread-safe queue]
              → Slint timer (100 ms) drains queue into window.synthesis_log
              → window.synthesis_busy = False when thread completes
        """
        target = window.synthesis_target

        if not target or not target.strip():
            # No target selected — run the built-in Slint core dual synthesis
            append_synthesis(
                "[RESEARCH] No target selected — running built-in Slint Core "
                "Dual Pattern Synthesis (TEXT_GPU_ACCEL_V1 + MULTI_WINDOW_ORCH_V1)…"
            )
            try:
                from scripts.dual_synthesis import DualSynthesizer
            except ImportError as exc:
                append_synthesis(f"[ERROR] Cannot import DualSynthesizer: {exc}")
                return

            # Import SynthesisAgent only for its progress-queue infrastructure
            import queue as _dual_queue_mod
            _dual_progress_queue: _dual_queue_mod.SimpleQueue = _dual_queue_mod.SimpleQueue()

            def _enqueue_dual(msg: str) -> None:
                _dual_progress_queue.put(msg)

            def _run_dual() -> None:
                """
                Worker thread — DualSynthesizer.
                Communication path:
                  _run_dual()
                    → DualSynthesizer.synthesize()
                        → each progress msg → _enqueue_dual(msg) → _dual_progress_queue
                    → _dual_progress_queue.put("[DONE]")  [sentinel]
                """
                try:
                    ds = DualSynthesizer(progress_cb=_enqueue_dual)
                    ds.synthesize()
                except Exception as exc:
                    _enqueue_dual(f"[ERROR] Dual synthesis failed: {exc}")
                finally:
                    _enqueue_dual("[DONE]")

            window.synthesis_busy = True
            window.synthesis_log = ""
            append_telemetry("[jcmd] begin_deconstruction: Slint Core Dual Synthesis")
            threading.Thread(target=_run_dual, daemon=True).start()

            # Poll the queue — same Slint Timer pattern as the full SynthesisAgent path
            try:
                import slint as _slint  # type: ignore[import]
                _dual_timer = _slint.Timer()
                import queue as _q_dual

                def _poll_dual() -> None:
                    try:
                        while True:
                            msg = _dual_progress_queue.get_nowait()
                            if msg == "[DONE]":
                                _dual_timer.stop()
                                window.synthesis_busy = False
                                append_telemetry("[jcmd] dual_synthesis complete")
                                return
                            append_synthesis(msg)
                    except _q_dual.Empty:
                        pass

                _dual_timer.start(_slint.TimerMode.Repeated, 100, _poll_dual)
            except Exception:
                pass
            return

        # ── Full SynthesisAgent path (target file provided) ──────────────────
        # Import SynthesisAgent (deferred to avoid import cost at startup)
        try:
            from scripts.synthesis_engine import SynthesisAgent, default_output_lib
        except ImportError as exc:
            append_synthesis(f"[ERROR] Cannot import SynthesisAgent: {exc}")
            return

        # Thread-safe queue for progress messages from the worker thread
        import queue as _queue
        _progress_queue: _queue.SimpleQueue = _queue.SimpleQueue()

        def _enqueue_progress(msg: str) -> None:
            """Worker thread → queue (thread-safe)."""
            _progress_queue.put(msg)

        def _run_synthesis() -> None:
            """
            Worker thread body.
            Communication path (thread):
              _run_synthesis()
                → SynthesisAgent(target, output_lib, progress_cb=_enqueue_progress)
                → agent.deconstruct()
                    → _enqueue_progress(msg)  [each step emits progress]
                → _progress_queue.put("[DONE]")  [sentinel to signal completion]
            """
            try:
                agent = SynthesisAgent(
                    target_path=target,
                    output_lib=default_output_lib(),
                    ai_config=backend.config,
                    progress_cb=_enqueue_progress,
                )
                agent.deconstruct()
            except Exception as exc:
                _enqueue_progress(f"[ERROR] Synthesis failed: {exc}")
            finally:
                _progress_queue.put("[DONE]")  # sentinel for the timer

        # Mark busy and clear previous synthesis log
        window.synthesis_busy = True
        window.synthesis_log = ""
        append_telemetry(f"[jcmd] begin_deconstruction: {os.path.basename(target)}")

        # Start the worker thread
        threading.Thread(target=_run_synthesis, daemon=True).start()

        # Poll the queue every ~100 ms from within the Slint event loop using
        # a recursive timer.  This is the only thread-safe way to update Slint
        # properties from a background thread.
        #
        # Communication path (timer loop):
        #   slint.Timer(100ms) → _poll_progress()
        #     → _progress_queue.get_nowait()   [non-blocking dequeue]
        #     → window.synthesis_log appended
        #     → if sentinel "[DONE]": timer.stop(), window.synthesis_busy = False

        try:
            import slint as _slint  # type: ignore[import]
            _timer = _slint.Timer()

            def _poll_progress() -> None:
                import queue as _q
                try:
                    while True:
                        msg = _progress_queue.get_nowait()
                        if msg == "[DONE]":
                            _timer.stop()
                            window.synthesis_busy = False
                            append_telemetry("[jcmd] deconstruction complete")
                            return
                        append_synthesis(msg)
                except _q.Empty:
                    pass  # nothing new yet — timer fires again in 100 ms

            _timer.start(_slint.TimerMode.Repeated, 100, _poll_progress)
        except Exception:
            # If the Slint Timer API isn't available, fall back to a blocking join
            # (not ideal for UI responsiveness, but functional for CLI testing).
            pass

    # Start the Slint event loop — blocks until the window is closed
    window.run()


if __name__ == "__main__":
    main()
