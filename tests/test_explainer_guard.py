from __future__ import annotations

import pytest

from finresearch_agent.llm.explainer import _validate_no_new_numbers


def test_validator_rejects_new_numbers():
    snapshot_json = '{"analysis_id":"abc","value":1.23}'
    _validate_no_new_numbers(snapshot_json, "analysis_id=abc; value=1.23")
    with pytest.raises(ValueError):
        _validate_no_new_numbers(snapshot_json, "analysis_id=abc; value=99")
