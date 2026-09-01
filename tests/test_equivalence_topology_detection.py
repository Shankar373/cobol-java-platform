import pytest
from execution.topology import detect_topology, observable_summary


def test_topology_multi_file_output():
    # >= 2 baseline files -> MULTI_FILE_OUTPUT
    files = {"out1.dat": b"some data", "out2.dat": b"other data"}
    res = detect_topology(files, {}, "stdout", "stdout")
    assert res == "MULTI_FILE_OUTPUT"


def test_topology_file_output():
    # exactly 1 baseline file -> FILE_OUTPUT
    files = {"out1.dat": b"some data"}
    res = detect_topology(files, {}, "stdout", "stdout")
    assert res == "FILE_OUTPUT"


def test_topology_console_output():
    # no files + non-empty baseline stdout -> CONSOLE_OUTPUT
    files = {}
    res = detect_topology(files, {}, "STARTO\nEND", "STARTO\nEND")
    assert res == "CONSOLE_OUTPUT"

    # check strip works
    res_spaces = detect_topology(files, {}, "   \n  ", "   ")
    assert res_spaces == "NO_OBSERVABLE_OUTPUT"


def test_topology_no_observable_output():
    # no files + empty/missing baseline stdout -> NO_OBSERVABLE_OUTPUT
    files = {}
    assert detect_topology(files, {}, "", "") == "NO_OBSERVABLE_OUTPUT"
    assert detect_topology(files, {}, None, None) == "NO_OBSERVABLE_OUTPUT"


def test_observable_summary():
    files = {"a.dat": b"123"}
    summary = observable_summary(files, {}, "stdout", "stdout")
    assert summary["topology"] == "FILE_OUTPUT"
    assert summary["legacy_observable"] == {"type": "files", "count": 1, "total_bytes": 3}
    assert summary["native_observable"] == {"type": "stdout", "chars": 6}

