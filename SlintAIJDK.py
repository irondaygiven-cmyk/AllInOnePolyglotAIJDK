#!/usr/bin/env python3
"""
AllInOnePolyglotAIJDK - Slint front-end entry point

Requires the 'slint' package (installed by AIDK_in.bat).
Shares the same AI-query logic as AllInOnePolyglotAIJDK.py but renders
its UI via Slint instead of PySide6 / QML.
"""

import os
import sys
import gzip
import json
import requests as _requests

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SLINT_FILE = os.path.join(_SCRIPT_DIR, "slint", "main.slint")


# ---------------------------------------------------------------------------
# AI / library logic (extracted from AllInOnePolyglotAIJDK.py)
# ---------------------------------------------------------------------------
class AIBackend:
    def __init__(self):
        self.config = {
            "provider": "lmstudio",
            "api_key": "",
            "base_url": "http://localhost:1234/v1",
            "model": "local-model",
            "temperature": 0.2,
        }
        self.chat_history = []
        self.current_environment = "java"
        self.is_planning_mode = True

        self.learning_library = []
        self.malicious_library = []

        self.SYSTEM_PREPEND = (
            "You are the world's best polyglot Java + GraalVM + AI engineer.\n"
            "You MUST build every project to the user's EXACT specification."
        )

    # ---- Library persistence ----

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

    # ---- AI query ----

    def query_ai(self, user_message: str) -> str:
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
            response = _requests.post(url, headers=headers, json=payload, timeout=120)
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return f"AI Error: {str(e)}"

    def send(self, text: str) -> str:
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


# ---------------------------------------------------------------------------
# Slint UI wiring
# ---------------------------------------------------------------------------
def main():
    try:
        import slint
    except ImportError:
        sys.exit(
            "ERROR: 'slint' package not found.\n"
            "Please run AIDK_in.bat to install dependencies first."
        )

    backend = AIBackend()
    backend.load_libraries()

    components = slint.load_file(_SLINT_FILE)
    window = components.MainWindow()

    # Keep a local copy of the message list that we append to.
    messages = []

    _APP_STATE_NAMES = {0: "Planning", 1: "Development", 2: "BrowserDev"}

    def append_message(text: str, is_user: bool):
        messages.append(slint.Struct({"text": text, "is-user": is_user}))
        window.chat_messages = messages

    def append_log(line: str):
        current = window.deploy_log or ""
        window.deploy_log = (current + "\n" + line).strip()

    def append_telemetry(line: str):
        current = window.telemetry_log or ""
        window.telemetry_log = (current + "\n" + line).strip()

    @window.send_message
    def on_send_message(text: str):
        if not text.strip():
            return
        append_message(text, is_user=True)
        window.status_text = "Thinking…"
        reply = backend.send(text)
        append_message(reply, is_user=False)
        append_log(f"[agent] responded ({len(reply)} chars)")
        append_telemetry(f"[jcmd] send_message: {len(text)} chars in, {len(reply)} chars out")
        window.status_text = "Ready"

    @window.set_environment
    def on_set_environment(env: str):
        backend.current_environment = env
        append_log(f"Environment set to: {env}")
        append_telemetry(f"[jcmd] environment -> {env}")

    @window.set_app_state
    def on_set_app_state(state):
        state_name = _APP_STATE_NAMES.get(int(state), str(state))
        backend.is_planning_mode = (state_name == "Planning")
        append_log(f"App state changed to: {state_name}")
        append_telemetry(f"[jcmd] app_state -> {state_name}")

    window.run()


if __name__ == "__main__":
    main()
