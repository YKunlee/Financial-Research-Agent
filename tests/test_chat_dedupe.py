from __future__ import annotations

from finresearch_agent.chat import append_message_dedup, dedupe_consecutive_messages


def test_dedupe_consecutive_messages_drops_repeats():
    msgs = [
        {"role": "assistant", "content": "x"},
        {"role": "assistant", "content": "x"},
        {"role": "user", "content": "y"},
        {"role": "assistant", "content": "x"},
        {"role": "assistant", "content": "x"},
    ]
    assert dedupe_consecutive_messages(msgs) == [
        {"role": "assistant", "content": "x"},
        {"role": "user", "content": "y"},
        {"role": "assistant", "content": "x"},
    ]


def test_append_message_dedup_skips_last_duplicate():
    msgs = [{"role": "assistant", "content": "no-info"}]
    msgs = append_message_dedup(msgs, role="assistant", content="no-info")
    assert msgs == [{"role": "assistant", "content": "no-info"}]


def test_append_message_dedup_merges_report_into_kept_item():
    msgs = [{"role": "assistant", "content": "found 1"}]
    report = {"ipos": [{"company_name": "Acme"}]}
    msgs = append_message_dedup(msgs, role="assistant", content="found 1", report=report)
    assert msgs == [{"role": "assistant", "content": "found 1", "report": report}]

