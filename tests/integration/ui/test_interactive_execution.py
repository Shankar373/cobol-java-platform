"""Regression tests for the generic interactive COBOL execution layer.

Tests are self-contained: all Docker calls are mocked so the suite runs
without Docker, GnuCOBOL, or Java installed.

Cases covered:
  A  Non-interactive COBOL             → no stdin injected, existing path used
  B  Interactive COBOL + smoke script  → scenario discovered, stdin generated
  C  Interactive COBOL, no scenario    → InteractiveInputRequired raised fast
  D  Interactive COBOL, scenario with extra stdin → output_limit/timeout guard
  E  Infinite loop                     → timeout fires, process killed
  F  Same scenario for COBOL and Java  → scenario_id identical
"""

import os
import sys
import tempfile
import textwrap
import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

# Project root is one level up
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from execution.interactive_detector import detect_interactivity, _is_interactive_accept
from execution.models import ExecutionScenario, InteractiveInputRequired
from execution.scenario_parser import parse_stdin_from_script
from execution.scenario_discovery import discover_scenario


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repo(tmp_dir: str, files: dict) -> str:
    """Write files dict {relpath: content} under tmp_dir and return path."""
    for relpath, content in files.items():
        full = os.path.join(tmp_dir, relpath)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    return tmp_dir


def _discover_data(entry: str, sources: list, program_ids: dict = None, call_graph: dict = None):
    """Build a minimal discover data dict."""
    return {
        "entry": entry,
        "sources": sources,
        "program_ids": program_ids or {s: os.path.splitext(os.path.basename(s))[0].upper()
                                       for s in sources},
        "call_graph": call_graph or {"edges": {}, "roots": [entry], "dynamic_callers": []},
        "output_dirs": ["data/out"],
    }


# ---------------------------------------------------------------------------
# Case A — Non-interactive COBOL
# ---------------------------------------------------------------------------

class TestNonInteractiveDetection(unittest.TestCase):

    def test_batch_program_has_no_accept(self):
        """A program with no ACCEPT is NON_INTERACTIVE."""
        with tempfile.TemporaryDirectory() as tmp:
            src = "src/BATCH.cob"
            _make_repo(tmp, {src: textwrap.dedent("""\
                IDENTIFICATION DIVISION.
                PROGRAM-ID. BATCH.
                PROCEDURE DIVISION.
                    MOVE 1 TO WS-FLAG.
                    STOP RUN.
            """)})
            d = _discover_data("BATCH", [src])
            result = detect_interactivity(tmp, d)
            self.assertEqual(result, "NON_INTERACTIVE")

    def test_accept_from_date_is_not_interactive(self):
        """ACCEPT WS-DATE FROM DATE must not trigger INTERACTIVE classification."""
        with tempfile.TemporaryDirectory() as tmp:
            src = "src/DATEONLY.cob"
            _make_repo(tmp, {src: textwrap.dedent("""\
                IDENTIFICATION DIVISION.
                PROGRAM-ID. DATEONLY.
                PROCEDURE DIVISION.
                    ACCEPT WS-TODAY FROM DATE.
                    ACCEPT WS-TIME FROM TIME.
                    ACCEPT WS-DAY FROM DAY-OF-WEEK.
                    STOP RUN.
            """)})
            d = _discover_data("DATEONLY", [src])
            result = detect_interactivity(tmp, d)
            self.assertEqual(result, "NON_INTERACTIVE")

    def test_accept_from_time_is_not_interactive(self):
        self.assertFalse(_is_interactive_accept("WS-TIME", "TIME"))

    def test_accept_from_day_is_not_interactive(self):
        self.assertFalse(_is_interactive_accept("WS-DAY", "DAY"))

    def test_bare_accept_is_interactive(self):
        self.assertTrue(_is_interactive_accept("WS-CHOICE", None))

    def test_accept_no_from_clause_is_interactive(self):
        """ACCEPT WS-MENU-CHOICE (no FROM) must classify as INTERACTIVE."""
        with tempfile.TemporaryDirectory() as tmp:
            src = "src/MENU.cob"
            _make_repo(tmp, {src: textwrap.dedent("""\
                IDENTIFICATION DIVISION.
                PROGRAM-ID. MENU.
                PROCEDURE DIVISION.
                    DISPLAY "Choose:".
                    ACCEPT WS-CHOICE.
                    STOP RUN.
            """)})
            d = _discover_data("MENU", [src])
            result = detect_interactivity(tmp, d)
            self.assertEqual(result, "INTERACTIVE")


# ---------------------------------------------------------------------------
# Case B — Interactive COBOL with shell smoke test
# ---------------------------------------------------------------------------

class TestScenarioParser(unittest.TestCase):

    def test_heredoc_extraction(self):
        """Only the heredoc body (not variable exports) is returned."""
        script = textwrap.dedent("""\
            #!/bin/bash
            export ACCOUNT_ID=10001
            export AMOUNT=5000
            ./bank <<EOF
            1
            10001
            5000
            9
            EOF
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as f:
            f.write(script)
            path = f.name
        try:
            values = parse_stdin_from_script(path)
        finally:
            os.unlink(path)
        # Must NOT contain ACCOUNT_ID=10001 or AMOUNT=5000 lines
        self.assertEqual(values, ["1", "10001", "5000", "9"])

    def test_printf_percent_s(self):
        """printf '%s\\n' val1 val2 | prog — extracts val1, val2."""
        script = "printf '%s\\n' 1 hello 9 | ./program\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as f:
            f.write(script)
            path = f.name
        try:
            values = parse_stdin_from_script(path)
        finally:
            os.unlink(path)
        self.assertIsNotNone(values)
        self.assertIn("1", values)
        self.assertIn("9", values)

    def test_echo_pipe(self):
        """echo "9" | prog — extracts 9."""
        script = 'echo "9" | ./bank\n'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False, encoding="utf-8") as f:
            f.write(script)
            path = f.name
        try:
            values = parse_stdin_from_script(path)
        finally:
            os.unlink(path)
        self.assertIsNotNone(values)
        self.assertIn("9", values)

    def test_missing_file_returns_none(self):
        result = parse_stdin_from_script("/nonexistent/path/script.sh")
        self.assertIsNone(result)


class TestScenarioDiscovery(unittest.TestCase):

    def test_smoke_script_discovered(self):
        """Smoke script under test/ is discovered and its stdin extracted."""
        with tempfile.TemporaryDirectory() as tmp:
            script = textwrap.dedent("""\
                #!/bin/bash
                ./program <<EOF
                1
                9
                EOF
            """)
            _make_repo(tmp, {"test/run_smoke_test.sh": script})
            d = _discover_data("MYMENU", ["src/MYMENU.cob"])
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir, exist_ok=True)

            scenario = discover_scenario(tmp, out_dir, d, {})
            self.assertEqual(scenario.entrypoint, "MYMENU")
            self.assertEqual(scenario.input_values, ["1", "9"])
            self.assertIn("test/run_smoke_test.sh", scenario.input_source)

    def test_stdin_file_discovered(self):
        """Fixture .stdin file under test/ is discovered."""
        with tempfile.TemporaryDirectory() as tmp:
            _make_repo(tmp, {"test/smoke.stdin": "1\n9\n"})
            d = _discover_data("PROG", ["src/PROG.cob"])
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir, exist_ok=True)

            scenario = discover_scenario(tmp, out_dir, d, {})
            self.assertIn("1", scenario.input_values)
            self.assertIn("9", scenario.input_values)

    def test_no_scenario_raises_interactive_input_required(self):
        """Without any scenario, InteractiveInputRequired must be raised."""
        with tempfile.TemporaryDirectory() as tmp:
            src = "src/MENU.cob"
            _make_repo(tmp, {src: "IDENTIFICATION DIVISION.\nPROGRAM-ID. MENU.\nPROCEDURE DIVISION.\nACCEPT WS-X.\n"})
            d = _discover_data("MENU", [src])
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir, exist_ok=True)

            with self.assertRaises(InteractiveInputRequired) as ctx:
                discover_scenario(tmp, out_dir, d, {})
            self.assertIn("INTERACTIVE_INPUT_REQUIRED", str(ctx.exception))


# ---------------------------------------------------------------------------
# Case D — Deterministic scenario_id
# ---------------------------------------------------------------------------

class TestScenarioId(unittest.TestCase):

    def test_scenario_id_is_deterministic(self):
        """Same inputs → same scenario_id."""
        sc1 = ExecutionScenario(
            entrypoint="MYMENU",
            input_source="test/smoke.sh",
            input_values=["1", "9"],
            stdin_path="/tmp/a.txt",
            expected_termination="unknown",
            timeout_seconds=120,
            max_output_bytes=5 * 1024 * 1024,
        )
        sc2 = ExecutionScenario(
            entrypoint="MYMENU",
            input_source="test/smoke.sh",
            input_values=["1", "9"],
            stdin_path="/tmp/different_path.txt",  # path differs — id must NOT
            expected_termination="unknown",
            timeout_seconds=120,
            max_output_bytes=5 * 1024 * 1024,
        )
        self.assertEqual(sc1.scenario_id, sc2.scenario_id)

    def test_different_inputs_give_different_id(self):
        """Different stdin values → different scenario_id."""
        sc1 = ExecutionScenario(
            entrypoint="MENU", input_source="test/s.sh",
            input_values=["1"], stdin_path="", expected_termination="unknown",
            timeout_seconds=120, max_output_bytes=1024 * 1024,
        )
        sc2 = ExecutionScenario(
            entrypoint="MENU", input_source="test/s.sh",
            input_values=["9"], stdin_path="", expected_termination="unknown",
            timeout_seconds=120, max_output_bytes=1024 * 1024,
        )
        self.assertNotEqual(sc1.scenario_id, sc2.scenario_id)


# ---------------------------------------------------------------------------
# Case F — Same scenario for COBOL and Java
# ---------------------------------------------------------------------------

class TestScenarioReuse(unittest.TestCase):

    def test_scenario_round_trips_through_json(self):
        """ExecutionScenario serializes/deserializes without losing scenario_id."""
        sc = ExecutionScenario(
            entrypoint="MYMENU",
            input_source="test/run_smoke.sh",
            input_values=["1", "10001", "5000", "9"],
            stdin_path="/out/execution/abc123/interactive_input.txt",
            expected_termination="unknown",
            timeout_seconds=120,
            max_output_bytes=5 * 1024 * 1024,
        )
        original_id = sc.scenario_id
        restored = ExecutionScenario.from_dict(sc.to_dict())
        self.assertEqual(original_id, restored.scenario_id)
        self.assertEqual(sc.input_values, restored.input_values)
        self.assertEqual(sc.entrypoint, restored.entrypoint)


# ---------------------------------------------------------------------------
# Case C — Fail fast on missing scenario
# ---------------------------------------------------------------------------

class TestFailFast(unittest.TestCase):

    def test_interactive_with_no_script_fails_fast(self):
        """Empty repo + interactive program → immediate InteractiveInputRequired."""
        with tempfile.TemporaryDirectory() as tmp:
            src = "src/INTERACTIVE.cob"
            _make_repo(tmp, {src: "IDENTIFICATION DIVISION.\nPROGRAM-ID. INTERACTIVE.\nPROCEDURE DIVISION.\nACCEPT WS-DATA.\nSTOP RUN.\n"})
            d = _discover_data("INTERACTIVE", [src])
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir, exist_ok=True)

            with self.assertRaises(InteractiveInputRequired):
                discover_scenario(tmp, out_dir, d, {})

    def test_explicit_config_scenario_used(self):
        """migration_config.json execution.interactive_scenario is honoured."""
        with tempfile.TemporaryDirectory() as tmp:
            script = "#!/bin/bash\n./prog <<EOF\n1\n9\nEOF\n"
            _make_repo(tmp, {
                "test/custom_input.sh": script,
                "src/PROG.cob": "",
            })
            d = _discover_data("PROG", ["src/PROG.cob"])
            out_dir = os.path.join(tmp, "out")
            os.makedirs(out_dir, exist_ok=True)
            cfg = {"execution": {"interactive_scenario": "test/custom_input.sh"}}
            # Remove default smoke scripts so only config path is found
            scenario = discover_scenario(tmp, out_dir, d, cfg)
            self.assertIn("custom_input.sh", scenario.input_source)


# ---------------------------------------------------------------------------
# Case E — Timeout / output-size guard (no Docker needed — test low-level runner)
# ---------------------------------------------------------------------------

class TestWatchdog(unittest.TestCase):

    def test_timeout_kills_process(self):
        """_run_with_watchdog kills a process that exceeds the timeout."""
        from execution.scenario_runner import _run_with_watchdog
        # Use a Python spin-loop as an infinite process (cross-platform)
        if sys.platform == "win32":
            cmd = [sys.executable, "-c", "import time; time.sleep(9999)"]
        else:
            cmd = [sys.executable, "-c", "import time; time.sleep(9999)"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            stdin_path = f.name
        try:
            rc, stdout, stderr, duration, status = _run_with_watchdog(
                cmd, stdin_path, timeout_seconds=2, max_output_bytes=10 * 1024 * 1024,
            )
        finally:
            os.unlink(stdin_path)

        self.assertEqual(status, "timeout")
        self.assertLess(duration, 10)  # must not run for 9999 s

    def test_output_limit_kills_process(self):
        """_run_with_watchdog kills a process that produces too much output."""
        from execution.scenario_runner import _run_with_watchdog
        # Produce lots of output quickly
        cmd = [sys.executable, "-c",
               "import sys; "
               "[sys.stdout.write('X' * 4096 + '\\n') or sys.stdout.flush() for _ in range(10000)]"]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            stdin_path = f.name
        try:
            rc, stdout, stderr, duration, status = _run_with_watchdog(
                cmd, stdin_path, timeout_seconds=30, max_output_bytes=50 * 1024,
            )
        finally:
            os.unlink(stdin_path)

        self.assertEqual(status, "output_limit")

    def test_normal_exit_is_normal(self):
        """A process that exits cleanly gets termination_status=normal."""
        from execution.scenario_runner import _run_with_watchdog
        cmd = [sys.executable, "-c", "print('hello')"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            stdin_path = f.name
        try:
            rc, stdout, stderr, duration, status = _run_with_watchdog(
                cmd, stdin_path, timeout_seconds=30, max_output_bytes=10 * 1024 * 1024,
            )
        finally:
            os.unlink(stdin_path)

        self.assertEqual(status, "normal")
        self.assertEqual(rc, 0)
        self.assertIn("hello", stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
