from __future__ import annotations

from pathlib import Path

from maine_family_law_llm.case_corpus_builder import _windows_launcher_vbs


ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_vbs_launcher_matches_quote_safe_generator() -> None:
    checked_in = (ROOT / "START_MAINE_FAMILY_LAW_LLM.vbs").read_text(
        encoding="ascii"
    )
    generated = _windows_launcher_vbs().replace("\r\n", "\n")

    assert checked_in == generated
    assert 'ExpandEnvironmentStrings("%ComSpec%")' in checked_in
    assert 'fso.BuildPath(root, "START_MAINE_FAMILY_LAW_LLM.cmd")' in checked_in
    assert "Chr(34) & Chr(34) & launcher" in checked_in
    assert 'shell.Run "cmd /c """"' not in checked_in


def test_vbs_launcher_has_no_unterminated_string_literal_pattern() -> None:
    launcher = _windows_launcher_vbs()

    for line in launcher.splitlines():
        # VBScript escapes a literal quote as a doubled quote. Removing those
        # leaves an even number of delimiters on every non-comment line.
        without_escaped_quotes = line.replace('""', "")
        assert without_escaped_quotes.count('"') % 2 == 0, line
