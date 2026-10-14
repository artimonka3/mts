"""Validate authored gold data, provenance and source references; no model evaluation."""

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator, FormatChecker

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures"
DATASET = json.loads((FIXTURES / "dialogues_v1.json").read_text())


def test_fixture_dataset_matches_its_json_schema():
    schema = json.loads((FIXTURES / "dialogue.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(DATASET)


def test_fixture_provenance_cannot_be_mistaken_for_measured_model_results():
    assert DATASET["synthetic"] and DATASET["text_only"] and DATASET["no_real_audio"]
    assert DATASET["split"] == "development_only"
    assert DATASET["annotation_source"] == "codex_authored_fixture"
    assert DATASET["human_review_status"] == "pending"
    assert all(value == "not_measured" for value in DATASET["measurement_status"].values())
    dialogues = DATASET["dialogues"]
    assert 20 <= len(dialogues) <= 30
    assert len({dialogue["id"] for dialogue in dialogues}) == len(dialogues)
    for dialogue in dialogues:
        assert dialogue["synthetic"] and dialogue["text_only"] and dialogue["no_real_audio"]
        assert all(segment["start_ms"] is None for segment in dialogue["segments"])
        assert all(segment["end_ms"] is None for segment in dialogue["segments"])


def test_gold_sources_match_exact_revision_segment_and_unicode_slice():
    for dialogue in DATASET["dialogues"]:
        segments = {segment["id"]: segment for segment in dialogue["segments"]}
        assert len(segments) == len(dialogue["segments"])
        assert [segment["position"] for segment in dialogue["segments"]] == list(
            range(len(segments))
        )
        gold = dialogue["gold"]
        sources = list(gold["key_phrases"])
        for item in gold["agreements"] + gold["events"]:
            sources.extend(item["evidence"])
        for source in sources:
            assert source["transcript_revision"] == dialogue["transcript_revision"]
            segment = segments[source["segment_id"]]
            start, end = source["start_cp"], source["end_cp"]
            assert 0 <= start < end <= len(segment["text"])
            assert segment["text"][start:end] == source["quote"]


def test_gold_dates_and_participants_preserve_call_context():
    for dialogue in DATASET["dialogues"]:
        participants = {person["id"] for person in dialogue["participants"]}
        assert len(participants) == len(dialogue["participants"])
        call_at = datetime.fromisoformat(dialogue["call_at"])
        assert call_at.tzinfo is not None
        assert call_at.utcoffset() == call_at.astimezone(ZoneInfo(dialogue["timezone"])).utcoffset()
        for segment in dialogue["segments"]:
            if segment["participant_id"] is not None:
                assert segment["participant_id"] in participants
        for agreement in dialogue["gold"]["agreements"]:
            for field in ("obligor_participant_id", "recipient_participant_id"):
                if agreement[field] is not None:
                    assert agreement[field] in participants
            due = agreement["due"]
            assert due["timezone"] == dialogue["timezone"]
            assert due["basis_call_at"] == dialogue["call_at"]
            if due["kind"] == "date_only":
                date.fromisoformat(due["date"])
            elif due["kind"] == "instant":
                assert datetime.fromisoformat(due["at"]).tzinfo is not None
            elif due["kind"] == "interval":
                assert datetime.fromisoformat(due["start"]) <= datetime.fromisoformat(due["end"])


def test_fixture_set_covers_negative_changes_ambiguity_and_unicode():
    dialogues = DATASET["dialogues"]
    assert any(not dialogue["gold"]["agreements"] for dialogue in dialogues)
    event_kinds = {event["kind"] for dialogue in dialogues for event in dialogue["gold"]["events"]}
    assert {"cancelled", "rescheduled", "corrected"} <= event_kinds
    assert any(
        agreement["due"]["ambiguous"]
        for dialogue in dialogues
        for agreement in dialogue["gold"]["agreements"]
    )
    assert any(
        any(ord(character) > 0xFFFF for character in segment["text"])
        for dialogue in dialogues
        for segment in dialogue["segments"]
    )
