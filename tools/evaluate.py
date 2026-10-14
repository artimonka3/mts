"""Compare externally supplied predictions; never manufacture model measurements."""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalized(text):
    return " ".join(str(text).casefold().split())


def due_signature(due):
    return {
        key: due.get(key)
        for key in ("kind", "date", "at", "start", "end", "timezone")
        if key in due
    }


def signature(item):
    return json.dumps(
        {
            "action": normalized(item.get("action", "")),
            "obligor_participant_id": item.get("obligor_participant_id"),
            "recipient_participant_id": item.get("recipient_participant_id"),
            "due": due_signature(item.get("due", {})),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def score(dataset, predictions=None):
    base = {
        "dataset_version": dataset.get("dataset_version"),
        "synthetic": dataset.get("synthetic", True),
        "human_review_status": dataset.get("human_review_status", "pending"),
        "split": dataset.get("split", "development_only"),
        "asr": {"status": "not_measured"},
        "model_accuracy_claim": None,
    }
    if predictions is None:
        return {**base, "status": "not_measured", "metrics": None}
    keywords_gold = keywords_pred = keywords_match = 0
    agreements_gold = agreements_pred = agreements_match = 0
    fields_total = fields_match = 0
    evaluated = 0
    for dialogue in dataset["dialogues"]:
        if dialogue["id"] not in predictions:
            continue
        evaluated += 1
        predicted = predictions[dialogue["id"]]
        gold = dialogue["gold"]
        gold_phrases = {normalized(x["quote"]) for x in gold.get("key_phrases", [])}
        pred_phrases = {normalized(x) for x in predicted.get("predicted_keywords", [])}
        keywords_gold += len(gold_phrases)
        keywords_pred += len(pred_phrases)
        keywords_match += len(gold_phrases & pred_phrases)
        actual = gold.get("agreements", [])
        forecast = predicted.get("agreements", [])
        gold_sigs = [signature(x) for x in actual]
        pred_sigs = [signature(x) for x in forecast]
        agreements_gold += len(gold_sigs)
        agreements_pred += len(pred_sigs)
        remaining = pred_sigs.copy()
        for value in gold_sigs:
            if value in remaining:
                agreements_match += 1
                remaining.remove(value)
        # Field comparison uses explicit gold_id, otherwise dialogue-order alignment.
        by_id = {x.get("gold_id"): x for x in forecast if x.get("gold_id")}
        for index, expected in enumerate(actual):
            candidate = by_id.get(expected.get("id"))
            if candidate is None:
                candidate = forecast[index] if index < len(forecast) else {}
            for field in (
                "action",
                "obligor_participant_id",
                "recipient_participant_id",
                "due",
            ):
                fields_total += 1
                wanted, received = expected.get(field), candidate.get(field)
                if field == "action":
                    same = normalized(wanted or "") == normalized(received or "")
                elif field == "due":
                    same = due_signature(wanted or {}) == due_signature(received or {})
                else:
                    same = field in candidate and wanted == received
                fields_match += int(same)
    ratio = lambda numerator, denominator: (
        numerator / denominator if denominator else None
    )
    return {
        **base,
        "status": "prediction_comparison" if evaluated else "not_measured",
        "evaluated_dialogues": evaluated,
        "dataset_dialogues": len(dataset["dialogues"]),
        "coverage": ratio(evaluated, len(dataset["dialogues"])),
        "method": "exact normalized phrases; exact business fields; gold_id/order field alignment",
        "metrics": {
            "keyword_exact_precision": ratio(keywords_match, keywords_pred),
            "keyword_exact_recall": ratio(keywords_match, keywords_gold),
            "agreement_exact_precision": ratio(agreements_match, agreements_pred),
            "agreement_exact_recall": ratio(agreements_match, agreements_gold),
            "field_exact_accuracy": ratio(fields_match, fields_total),
        }
        if evaluated
        else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=ROOT / "fixtures/dialogues_v1.json"
    )
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    dataset = json.loads(arguments.dataset.read_text())
    predictions = (
        json.loads(arguments.predictions.read_text()) if arguments.predictions else None
    )
    result = json.dumps(score(dataset, predictions), ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.write_text(result + "\n")
    else:
        print(result)


if __name__ == "__main__":
    main()
