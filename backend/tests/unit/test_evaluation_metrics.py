import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[3] / "tools/evaluate.py"
spec = importlib.util.spec_from_file_location("evaluate_cli", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def dataset():
    return {
        "dialogues": [
            {
                "id": "one",
                "gold": {
                    "key_phrases": [{"quote": "Пришлю КП завтра"}],
                    "agreements": [
                        {
                            "id": "g1",
                            "action": "Отправить КП",
                            "obligor_participant_id": "p1",
                            "recipient_participant_id": "p2",
                            "due": {
                                "kind": "date_only",
                                "date": "2026-10-17",
                                "timezone": "Europe/Minsk",
                            },
                        }
                    ],
                },
            }
        ]
    }


def test_no_predictions_does_not_claim_accuracy():
    result = module.score(dataset())
    assert result["status"] == "not_measured" and result["metrics"] is None
    assert result["asr"]["status"] == "not_measured"
    assert result["model_accuracy_claim"] is None


def test_all_wrong_fields_are_zero_not_quality_90():
    result = module.score(
        dataset(),
        {
            "one": {
                "predicted_keywords": ["другое"],
                "agreements": [
                    {
                        "action": "Позвонить",
                        "obligor_participant_id": "wrong",
                        "recipient_participant_id": "wrong",
                        "due": {"kind": "unknown"},
                    }
                ],
            }
        },
    )
    assert all(value == 0 for value in result["metrics"].values())
    assert result["coverage"] == 1 and result["asr"]["status"] == "not_measured"
