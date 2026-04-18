#!/usr/bin/env python3
"""
scripts/synthesis_engine.py  —  AllInOnePolyglotAIJDK  Pattern Synthesis Engine

Implements the Learning_Library Building Process.  Given a target binary or
script, the SynthesisAgent deconstructs it to extract "Operative DNA" (memory
maps, API surfaces, logic patterns, UI layouts) and stores the results as
discrete JSON pattern files in the Learning_Library for future Assembly.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Communication paths
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Static Analysis (no code execution on the host)
     deconstruct()
       → _run_static_analysis(target)
           MSVC binary (.exe / .dll):
             subprocess.run(["dumpbin", "/EXPORTS", "/IMPORTS", target])
                 → raw_exports + raw_imports strings (stdout)
           Java bytecode (.class / .jar):
             subprocess.run(["javap", "-c", "-p", target])
                 → raw_bytecode string (stdout)
           Script (.py / .js / .rs / etc.):
             open(target).read()
                 → raw_source string
       ← dict {"exports": ..., "imports": ..., "bytecode": ..., "source": ...}

  2. AI-powered Pattern Extraction
     deconstruct()
       → _extract_patterns_via_ai(raw_analysis, target_name)
           → HTTP POST  {base_url}/chat/completions
             headers:   Content-Type: application/json
             body:      {"model": ..., "messages": [system + user], "stream": false}
             system:    Pattern Synthesis system prompt
             user:      raw_analysis dict serialised to text
           ← JSON  {"choices":[{"message":{"content":"<structured patterns>"}}]}
       ← str  AI-generated pattern description

  3. Pattern File Persistence
     deconstruct()
       → _save_pattern_file(target_name, analysis, ai_patterns)
           → JSON file written to:
               {output_lib}/{stem}_patterns.json
               where output_lib defaults to:
                 Windows: L:\\Learning_Library\\Synthesized_Data
                 Fallback: <repo_root>/Learning_Library/Synthesized_Data
       ← str  path to the written JSON file

  4. Progress streaming to caller (UI integration)
     Each major step calls self._progress(message) — a callable supplied by
     the caller (e.g. the Slint or QML UI layer) so the UI can update without
     polling.

     UI Integration example (SlintAIJDK.py):
       agent = SynthesisAgent(
           target_path   = window.synthesis_target,
           output_lib    = default_output_lib(),
           progress_cb   = lambda msg: append_synthesis_log(msg),
       )
       threading.Thread(target=agent.deconstruct, daemon=True).start()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern File Schema
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  {
    "Schema_Version":          "1.0",
    "Origin_Source":           "Legacy_Monitor_App.exe",
    "Synthesis_Date":          "2026-04-18",
    "Synthesis_Engine":        "AllInOnePolyglotAIJDK/scripts/synthesis_engine.py",
    "Deconstructed_Components": {
      "Memory_Map":            "...",   // offsets, thermal sensor hooks, etc.
      "API_Surface":           "...",   // exported/imported symbols
      "Logic_Patterns":        "...",   // control flow, algorithm signatures
      "UI_Layout":             "...",   // detected widget/layout patterns
      "JFR_Signature":         "..."    // low-overhead interrupt / profiling hooks
    },
    "Raw_Analysis_Excerpt":    "...",   // first 4 KB of static analysis output
    "AI_Pattern_Description":  "...",   // full AI extraction text
    "Assembly_Instruction":    "// Import via: use patterns::{stem};"
  }

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import requests

# ─────────────────────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────────────────────

# The canonical Windows output path for Learning_Library pattern files.
# Falls back to a local directory if the drive isn't mounted (e.g. on Linux CI).
_WINDOWS_OUTPUT_LIB = r"L:\Learning_Library\Synthesized_Data"
_LOCAL_OUTPUT_LIB = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "Learning_Library", "Synthesized_Data",
)


def default_output_lib() -> str:
    """
    Return the Learning_Library output path.

    Communication path
    ──────────────────
      default_output_lib()
        → checks os.path.exists(_WINDOWS_OUTPUT_LIB)
            True  → returns _WINDOWS_OUTPUT_LIB  (Windows production path)
            False → returns _LOCAL_OUTPUT_LIB    (local fallback, auto-created)
    """
    if os.path.exists(os.path.splitdrive(_WINDOWS_OUTPUT_LIB)[0] + "\\"):
        return _WINDOWS_OUTPUT_LIB
    return _LOCAL_OUTPUT_LIB


# ─────────────────────────────────────────────────────────────────────────────
# Static-analysis helpers
# ─────────────────────────────────────────────────────────────────────────────

# File extensions routed to each analysis tool.
_MSVC_EXTENSIONS = {".exe", ".dll", ".lib", ".obj"}
_JAVA_EXTENSIONS = {".class", ".jar"}
_SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".rs", ".go", ".cs", ".java",
                      ".c", ".cpp", ".h", ".hpp", ".rb", ".swift", ".kt"}


def _run_subprocess_safe(args: list, label: str) -> str:
    """
    Run a subprocess and return its stdout as a string.
    Never raises — returns an error description on failure.

    Communication path
    ──────────────────
      _run_subprocess_safe(args, label)
        → subprocess.run(args, capture_output=True, timeout=60)
        ← stdout decoded as UTF-8 (errors replaced)
        On failure: ← "[label] not available: <reason>"
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            timeout=60,
        )
        text = result.stdout.decode("utf-8", errors="replace")
        if not text.strip() and result.stderr:
            text = result.stderr.decode("utf-8", errors="replace")
        return text or f"[{label}] produced no output"
    except FileNotFoundError:
        return f"[{label}] tool not found on PATH — install {args[0]} to enable this analysis"
    except subprocess.TimeoutExpired:
        return f"[{label}] timed out after 60 s"
    except Exception as exc:
        return f"[{label}] error: {exc}"


def _read_source_file(path: str) -> str:
    """
    Read a script/source file directly.

    Communication path
    ──────────────────
      _read_source_file(path)
        → open(path, encoding="utf-8", errors="replace").read()
        ← file content (truncated at 64 KB to avoid huge payloads)
        On failure: ← error message string
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            content = fh.read(65536)  # 64 KB cap
        if len(content) == 65536:
            content += "\n... [truncated at 64 KB] ..."
        return content
    except Exception as exc:
        return f"[source reader] error: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# SynthesisAgent
# ─────────────────────────────────────────────────────────────────────────────

class SynthesisAgent:
    """
    Performs the Learning_Library Building Process on a single target.

    Parameters
    ──────────
      target_path  : str  — full path to the binary, class file, or script.
      output_lib   : str  — directory where pattern JSON files are written.
                            Defaults to default_output_lib().
      ai_config    : dict — AI endpoint config (provider, base_url, model,
                            temperature, api_key). Defaults to LM Studio.
      progress_cb  : callable(str) → None
                            Called with a human-readable progress message at
                            each major step. Use this to stream updates to the
                            UI (Slint synthesis-log or QML TextArea).

    Usage (threaded, from SlintAIJDK.py or AllInOnePolyglotAIJDK.py)
    ──────────────────────────────────────────────────────────────────
      agent = SynthesisAgent(
          target_path = "/path/to/target.exe",
          progress_cb = lambda msg: window.synthesis_log += "\\n" + msg,
      )
      threading.Thread(target=agent.deconstruct, daemon=True).start()
    """

    # System prompt used for all AI pattern-extraction requests.
    # Avoids the term "reverse engineer"; uses "Pattern Synthesis" throughout.
    _SYNTHESIS_SYSTEM_PROMPT = (
        "You are the AllInOnePolyglotAIJDK Pattern Synthesis Agent. "
        "Your task is to assist in the Learning_Library Building Process. "
        "Analyze the provided static analysis output and identify modular Patterns. "
        "Extract: (1) memory offsets and data structures, (2) API / symbol surface, "
        "(3) control flow and algorithm signatures, (4) UI layout patterns if present, "
        "(5) JFR-compatible low-overhead diagnostic hooks. "
        "Document findings as structured JSON-compatible text with clear section headers. "
        "Use the term 'Pattern Synthesis' — not 'reverse engineering'. "
        "Be concise but complete. Focus on reusable, composable components."
    )

    def __init__(
        self,
        target_path: str,
        output_lib: Optional[str] = None,
        ai_config: Optional[dict] = None,
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.target = target_path
        self.output_lib = output_lib or default_output_lib()
        self.progress_cb = progress_cb or (lambda msg: print(f"[synthesis] {msg}"))
        # AI endpoint configuration — mirrors AIBackend.config
        self.ai_config = ai_config or {
            "provider": "lmstudio",
            "api_key": "",
            "base_url": "http://localhost:1234/v1",
            "model": "local-model",
            "temperature": 0.15,  # lower temp for structured analytical output
        }

    # ── Public API ─────────────────────────────────────────────────────────────

    def deconstruct(self) -> Optional[str]:
        """
        Execute the full Learning_Library Building Process on self.target.

        Steps
        ─────
          1. Validate target path
          2. Static analysis  → raw analysis dict
          3. AI pattern extraction → pattern description string
          4. Save JSON pattern file → output path
          5. Emit progress at each step via self.progress_cb

        Returns the path of the saved pattern file, or None on fatal error.

        Communication path
        ──────────────────
          deconstruct()
            → _validate_target()
            → _run_static_analysis()
                → subprocess (dumpbin / javap) OR file read
            → _extract_patterns_via_ai()
                → HTTP POST  {base_url}/chat/completions
                ← AI pattern description
            → _save_pattern_file()
                → json.dump → {output_lib}/{stem}_patterns.json
            → progress_cb(msg) at each step  [→ Slint/QML UI update]
        """
        self._progress(f"[RESEARCH] Starting Pattern Synthesis on: {self.target}")

        # 1. Validate
        if not self._validate_target():
            return None

        # 2. Static analysis
        self._progress("[RESEARCH] Step 1/3 — Running static analysis…")
        raw_analysis = self._run_static_analysis()

        # 3. AI pattern extraction
        self._progress("[RESEARCH] Step 2/3 — Extracting patterns via AI…")
        ai_patterns = self._extract_patterns_via_ai(raw_analysis)

        # 4. Save pattern file
        self._progress("[RESEARCH] Step 3/3 — Saving pattern file to Learning_Library…")
        out_path = self._save_pattern_file(raw_analysis, ai_patterns)

        if out_path:
            self._progress(f"[SUCCESS] Pattern Synthesis complete. File: {out_path}")
        return out_path

    # ── Internal steps ─────────────────────────────────────────────────────────

    def _validate_target(self) -> bool:
        """
        Check that the target path exists and is a readable file.

        Communication path
        ──────────────────
          _validate_target()
            → os.path.isfile(self.target)
            → progress_cb("[ERROR] ...")  on failure
        """
        if not os.path.isfile(self.target):
            self._progress(f"[ERROR] Target not found or is not a file: {self.target}")
            return False
        self._progress(f"[OK] Target validated: {os.path.basename(self.target)}")
        return True

    def _run_static_analysis(self) -> dict:
        """
        Route the target to the appropriate static analysis tool.

        Communication path
        ──────────────────
          _run_static_analysis()
            MSVC binary → _run_subprocess_safe(["dumpbin", "/EXPORTS", "/IMPORTS", target])
            Java bytecode → _run_subprocess_safe(["javap", "-c", "-p", target])
            Script/source → _read_source_file(target)
            Unknown        → _read_source_file(target)  [best-effort text read]
        """
        ext = Path(self.target).suffix.lower()
        analysis: dict = {
            "target": self.target,
            "extension": ext,
            "exports": "",
            "imports": "",
            "bytecode": "",
            "source": "",
        }

        if ext in _MSVC_EXTENSIONS:
            # MSVC PE binary — use dumpbin (part of MSVC toolchain / VS Build Tools)
            self._progress("[ANALYSIS] Running dumpbin /EXPORTS /IMPORTS…")
            analysis["exports"] = _run_subprocess_safe(
                ["dumpbin", "/EXPORTS", self.target], "dumpbin-exports"
            )
            analysis["imports"] = _run_subprocess_safe(
                ["dumpbin", "/IMPORTS", self.target], "dumpbin-imports"
            )

        elif ext in _JAVA_EXTENSIONS:
            # Java bytecode / JAR — use javap (part of any JDK installation)
            self._progress("[ANALYSIS] Running javap -c -p…")
            analysis["bytecode"] = _run_subprocess_safe(
                ["javap", "-c", "-p", self.target], "javap"
            )

        else:
            # Script or source file — read directly (no execution on host)
            self._progress(f"[ANALYSIS] Reading source file ({ext})…")
            analysis["source"] = _read_source_file(self.target)

        total_chars = sum(len(v) for v in analysis.values() if isinstance(v, str))
        self._progress(f"[ANALYSIS] Collected {total_chars:,} chars of analysis data")
        return analysis

    def _extract_patterns_via_ai(self, raw_analysis: dict) -> str:
        """
        Send the raw analysis to the AI for structured pattern extraction.

        Communication path
        ──────────────────
          _extract_patterns_via_ai(raw_analysis)
            → Build user prompt from raw_analysis dict (truncated excerpts)
            → HTTP POST  {base_url}/chat/completions
              headers: Content-Type: application/json
                       Authorization: Bearer {api_key}  (non-LM-Studio only)
              body:    {"model": ..., "messages": [system, user],
                        "temperature": 0.15, "stream": false}
            ← JSON  {"choices":[{"message":{"content":"<patterns>"}}]}
            On error: ← error description string (never raises)
        """
        # Build a concise user prompt from the analysis data
        excerpt_limit = 8000  # chars per field to stay within context window
        parts = []
        if raw_analysis.get("exports"):
            parts.append(f"=== EXPORTS ===\n{raw_analysis['exports'][:excerpt_limit]}")
        if raw_analysis.get("imports"):
            parts.append(f"=== IMPORTS ===\n{raw_analysis['imports'][:excerpt_limit]}")
        if raw_analysis.get("bytecode"):
            parts.append(f"=== BYTECODE ===\n{raw_analysis['bytecode'][:excerpt_limit]}")
        if raw_analysis.get("source"):
            parts.append(f"=== SOURCE ===\n{raw_analysis['source'][:excerpt_limit]}")

        if not parts:
            return "[AI extraction skipped — no analysis data available]"

        target_name = os.path.basename(raw_analysis["target"])
        user_prompt = (
            f"Perform Pattern Synthesis on: {target_name}\n\n"
            + "\n\n".join(parts)
            + "\n\nExtract all reusable Operative DNA patterns as described."
        )

        try:
            url = f"{self.ai_config['base_url']}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if self.ai_config.get("provider") != "lmstudio" and self.ai_config.get("api_key"):
                # Cloud providers (OpenAI-compatible) require a Bearer token
                headers["Authorization"] = f"Bearer {self.ai_config['api_key']}"
            payload = {
                "model": self.ai_config["model"],
                "messages": [
                    {"role": "system", "content": self._SYNTHESIS_SYSTEM_PROMPT},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": self.ai_config["temperature"],
                "stream": False,
            }
            response = requests.post(url, headers=headers, json=payload, timeout=180)
            # Raise HTTPError for non-2xx status codes so the except block
            # produces a clear message including the status code and body excerpt.
            response.raise_for_status()
            data = response.json()
            result = data["choices"][0]["message"]["content"]
            self._progress(f"[AI] Pattern extraction complete ({len(result):,} chars)")
            return result
        except requests.HTTPError as exc:
            # Include status code and first 500 chars of body for diagnostics
            body_excerpt = ""
            try:
                body_excerpt = exc.response.text[:500]
            except Exception:
                pass
            msg = f"[AI extraction HTTP error] {exc.response.status_code}: {body_excerpt}"
            self._progress(msg)
            return msg
        except (KeyError, IndexError, ValueError) as exc:
            msg = f"[AI extraction parse error] Unexpected response structure: {exc}"
            self._progress(msg)
            return msg
        except Exception as exc:
            msg = f"[AI extraction error] {exc}"
            self._progress(msg)
            return msg

    def _save_pattern_file(self, raw_analysis: dict, ai_patterns: str) -> Optional[str]:
        """
        Persist the pattern data as a JSON file in output_lib.

        Communication path
        ──────────────────
          _save_pattern_file(raw_analysis, ai_patterns)
            → os.makedirs(output_lib, exist_ok=True)
            → json.dump(pattern_doc, file)
                → {output_lib}/{stem}_patterns.json
            → progress_cb("Saved: <path>")
            ← path str on success, None on error

        The generated pattern file follows the schema documented at the top of
        this module.  The Assembly_Instruction field provides the Rust import
        hint for use in the Development Assembly phase.
        """
        stem = Path(self.target).stem
        # Sanitise stem for use as a filename
        safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)
        out_path = os.path.join(self.output_lib, f"{safe_stem}_patterns.json")

        # Build the raw analysis excerpt (first 4 KB for the pattern file)
        raw_excerpt = ""
        for key in ("exports", "imports", "bytecode", "source"):
            val = raw_analysis.get(key, "")
            if val and not val.startswith("["):
                raw_excerpt = val[:4096]
                break

        pattern_doc = {
            "Schema_Version": "1.0",
            "Origin_Source": os.path.basename(self.target),
            "Synthesis_Date": datetime.now().strftime("%Y-%m-%d"),
            "Synthesis_Engine": "AllInOnePolyglotAIJDK/scripts/synthesis_engine.py",
            "Deconstructed_Components": {
                # These fields are populated from the AI's structured output.
                # The AI is prompted to include these sections explicitly.
                "Memory_Map":      self._extract_section(ai_patterns, "Memory_Map",     "Memory", "Offset"),
                "API_Surface":     self._extract_section(ai_patterns, "API_Surface",    "API",    "Symbol"),
                "Logic_Patterns":  self._extract_section(ai_patterns, "Logic_Patterns", "Logic",  "Algorithm"),
                "UI_Layout":       self._extract_section(ai_patterns, "UI_Layout",      "UI",     "Widget"),
                "JFR_Signature":   self._extract_section(ai_patterns, "JFR_Signature",  "JFR",    "Interrupt"),
            },
            "Raw_Analysis_Excerpt": raw_excerpt,
            "AI_Pattern_Description": ai_patterns,
            # Rust import hint for the Assembly phase in Development mode
            "Assembly_Instruction": f"// Import via: use patterns::{safe_stem};",
        }

        try:
            os.makedirs(self.output_lib, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(pattern_doc, fh, indent=2, ensure_ascii=False)
            self._progress(f"[SAVED] {out_path}")
            return out_path
        except Exception as exc:
            self._progress(f"[ERROR] Could not write pattern file: {exc}")
            return None

    # ── Utilities ──────────────────────────────────────────────────────────────

    def _progress(self, message: str) -> None:
        """
        Emit a progress message via the caller-supplied callback.

        Communication path
        ──────────────────
          _progress(message)
            → self.progress_cb(message)
                → [Slint] window.synthesis_log updated (via SlintAIJDK.py timer)
                → [QML]   deployLogUpdated.emit(message) (via Backend slot)
        """
        try:
            self.progress_cb(message)
        except Exception:
            # Never let a UI callback failure abort the synthesis pipeline
            print(f"[synthesis progress] {message}", file=sys.stderr)

    @staticmethod
    def _extract_section(text: str, *keywords: str) -> str:
        """
        Heuristically extract the first paragraph that contains any of the
        supplied keywords from the AI's free-text pattern description.

        Communication path: pure in-process text processing; no I/O.
        """
        if not text:
            return ""
        lower = text.lower()
        for kw in keywords:
            idx = lower.find(kw.lower())
            if idx != -1:
                # Return up to 500 chars from the found position
                end = min(idx + 500, len(text))
                # Trim at the next blank line if one exists within the window
                snippet = text[idx:end]
                blank = snippet.find("\n\n")
                return snippet[:blank].strip() if blank != -1 else snippet.strip()
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry-point (for manual testing outside the GUI)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python synthesis_engine.py <target_path> [output_lib]")
        sys.exit(1)

    target = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else default_output_lib()

    agent = SynthesisAgent(
        target_path=target,
        output_lib=out,
        progress_cb=lambda msg: print(msg),
    )
    result = agent.deconstruct()
    sys.exit(0 if result else 1)
