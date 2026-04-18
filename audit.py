import subprocess
import os

def run_isolated_audit(project_name):
    path = f"L:\\ALLINONEPOLYGLOTAIJDK\\sandbox\\{project_name}"

    # 1. Compile via MSVC
    print(f"--- Compiling {project_name} ---")
    build = subprocess.run(["cargo", "build", "--release"], cwd=path, capture_output=True)

    if build.returncode != 0:
        print("Build Failed. Check syntax.")
        return False

    # 2. Detonate in Sandbox & Monitor with JFR
    print("--- Starting JFR Diagnostic Sweep ---")
    # This invokes jcmd on the new process to check for malicious resource spikes
    # jcmd <pid> JFR.start
