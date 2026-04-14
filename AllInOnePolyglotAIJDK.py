#!/usr/bin/env python3
"""
AllInOnePolyglotAIJDK v3.3 - PySide6 Optimized for Windows
Robust dependency installation (PySide6 + requests + local wheel)
"""

import sys
import os
import subprocess
import venv
import gzip
import json
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

    print("Installing PySide6, requests, and slint...")
    subprocess.check_call([venv_pip, "install", "PySide6", "requests", "slint"])

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


class Backend(QObject):
    chatUpdated = Signal(str)
    deployLogUpdated = Signal(str)
    terminalOutput = Signal(str)

    def __init__(self):
        super().__init__()
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

        self.SYSTEM_PREPEND = (
            "You are the world's best polyglot Java + GraalVM + AI engineer.\n"
            "You MUST build every project to the user's EXACT specification."
        )

        self.SYSTEM_PREPEND_DEVTOOLS = (
            "You are an expert Browser DevTools Controller Agent."
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

    # ---- Slots ----

    @Slot()
    def viewLibraries(self):
        self.load_libraries()
        self.deployLogUpdated.emit(
            f"JS-Learning_Library: {len(self.learning_library)} scripts\n"
            f"JS-Mal_LL: {len(self.malicious_library)} malicious scripts"
        )

    @Slot(str)
    def sendToAgent(self, text):
        if not text.strip():
            return
        self.chat_history.append({"role": "user", "content": text})
        reply = self.query_ai(text)
        self.chat_history.append({"role": "assistant", "content": reply})
        self.chatUpdated.emit(reply)
        self.save_libraries()

    @Slot(str)
    def setEnvironment(self, env):
        self.current_environment = env

    @Slot(bool)
    def togglePlanning(self, enabled):
        self.is_planning_mode = enabled

    @Slot(bool)
    def toggleDevTools(self, enabled):
        self.is_devtools_enabled = enabled
        self.deployLogUpdated.emit(
            f"DevTools Integration {'ENABLED' if enabled else 'DISABLED'}"
        )

    @Slot()
    def recreateAndSecurityScan(self):
        if not self.is_devtools_enabled:
            self.deployLogUpdated.emit("DevTools must be enabled first.")
            return
        self.deployLogUpdated.emit("Recreating page and running security scan...")
        self.sendToAgent(
            "Recreate the current webpage, sandbox it, and run JavaScript to check "
            "for malicious scripts and explore configurations."
        )

    @Slot(str)
    def sendDevToolsCommand(self, command):
        if not self.is_devtools_enabled:
            self.deployLogUpdated.emit("DevTools not enabled.")
            return
        self.deployLogUpdated.emit(f"Executing: {command}")

    @Slot()
    def openJavaToolkitDownload(self):
        webbrowser.open("https://adoptium.net/temurin/releases/")
        self.deployLogUpdated.emit("Opened Java Development Toolkit download page")

    @Slot()
    def checkJavaToolkit(self):
        try:
            result = subprocess.run(
                ["java", "-version"], capture_output=True, text=True, shell=True
            )
            self.deployLogUpdated.emit(
                f"Java Development Toolkit detected:\n{result.stderr.strip()}"
            )
        except Exception:
            self.deployLogUpdated.emit("Java Development Toolkit not found.")

    @Slot(str)
    def createProjectWithBuildSystem(self, system_type):
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
        try:
            result = subprocess.run(
                ["git", "--version"], capture_output=True, text=True, shell=True
            )
            self.deployLogUpdated.emit(f"Git detected: {result.stdout.strip()}")
        except Exception:
            self.deployLogUpdated.emit("Git not found.")

    @Slot()
    def openGitDownload(self):
        webbrowser.open("https://git-scm.com/download/win")
        self.deployLogUpdated.emit("Opened Git for Windows download page.")

    @Slot(str)
    def runGitCommand(self, command):
        self.deployLogUpdated.emit(f"Running: git {command}")
        try:
            result = subprocess.run(
                f"git {command}", capture_output=True, text=True, shell=True
            )
            output = result.stdout.strip() if result.stdout else result.stderr.strip()
            self.deployLogUpdated.emit(output)
        except Exception as e:
            self.deployLogUpdated.emit(f"Git error: {e}")

    @Slot(str, bool)
    def runSystemCommandShell(self, command, runAsAdmin):
        if self.terminal_process and self.terminal_process.state() == QProcess.Running:
            self.deployLogUpdated.emit("Stopping previous process...")
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
        try:
            with open("theme_layout.json", "w") as f:
                json.dump(self.current_theme, f, indent=4)
            self.deployLogUpdated.emit("Theme layout saved to theme_layout.json")
        except Exception as e:
            self.deployLogUpdated.emit(f"Failed to save theme: {e}")

    @Slot()
    def loadThemeLayout(self):
        try:
            with open("theme_layout.json", "r") as f:
                self.current_theme = json.load(f)
            self.deployLogUpdated.emit("Theme layout loaded successfully")
        except Exception:
            self.deployLogUpdated.emit("No saved theme found.")

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
        self.deployLogUpdated.emit("Theme reset to default")

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
