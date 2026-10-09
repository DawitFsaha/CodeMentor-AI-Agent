from __future__ import annotations

from codementor_ai.ui import _generated_source, diff_html, diff_stats


def test_diff_stats_counts_added_and_removed_lines():
    original = "a = 1\nb = 2\nc = 3\n"
    proposed = "a = 1\nb = 20\nc = 3\nd = 4\n"
    assert diff_stats(original, proposed) == (2, 1)
    assert diff_stats("", "x\ny\n") == (2, 0)


def test_diff_html_marks_lines_and_escapes_code():
    rendered = diff_html("print('<old>')\n", "print('<new>')\n")
    assert 'cm-diff-del">-print(&#x27;&lt;old&gt;&#x27;)' in rendered
    assert 'cm-diff-add">+print(&#x27;&lt;new&gt;&#x27;)' in rendered
    assert "<new>" not in rendered
    assert "No changes" in diff_html("same\n", "same\n")


def test_generated_source_only_proposes_fenced_code():
    assert _generated_source("Here:\n```python\nx = 1\n```\nDone") == "x = 1\n"
    assert _generated_source("I could not write code for this.") == ""
