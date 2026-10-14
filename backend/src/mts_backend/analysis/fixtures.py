"""Allowlisted synthetic text fixtures; never an ASR or LLM implementation."""

import json
from pathlib import Path

from mts_backend.core.business import BusinessError

DEFAULT_FIXTURE_PATH = Path(__file__).resolve().parents[4] / "fixtures" / "dialogues_v1.json"


def load_dataset(path=None):
    return json.loads(Path(path or DEFAULT_FIXTURE_PATH).read_text(encoding="utf-8"))


def get_scenario(scenario_id, path=None):
    dataset = load_dataset(path)
    found = next((d for d in dataset["dialogues"] if d["id"] == scenario_id), None)
    if not found:
        raise BusinessError(404, "not_found", "Demo scenario not found.")
    return found


def fixture_matches(call, transcript, scenario):
    return (
        call.is_demo
        and call.scenario_id == scenario["id"]
        and call.call_at.isoformat()
        == __import__("datetime")
        .datetime.fromisoformat(scenario["call_at"])
        .astimezone(call.call_at.tzinfo)
        .isoformat()
        and call.timezone == scenario["timezone"]
        and [(s["position"], s["text"], s.get("speaker_id")) for s in transcript.segments]
        == [(s["position"], s["text"], s.get("speaker_id")) for s in scenario["segments"]]
    )


def provenance():
    return {
        "source": "fixture",
        "is_demo": True,
        "synthetic": True,
        "text_only": True,
        "no_real_audio": True,
        "annotation_source": "codex_authored_fixture",
        "human_review_status": "pending",
        "measurement_status": "not_measured",
    }
