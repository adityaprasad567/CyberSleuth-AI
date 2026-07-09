"""
Feature 4: Incident Timeline Generator.

Builds a chronological timeline from two sources:
  1. Timestamps mentioned directly in the user's own description (sentence-level)
  2. Timestamps found in uploaded evidence (via evidence/extraction.py)

This is rule-based/regex-based, not LLM-based: reordering events correctly
matters for a legal document, and a deterministic sort by parsed time is
more trustworthy than an LLM re-summarizing a sequence (which risks subtly
reordering or dropping an event). Events without a parseable time are kept
in their original order, appended after any timed events for that source.
"""
import re
import sys
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).parent.parent / "evidence"))
from extraction import PATTERNS

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _parse_time_to_minutes(time_str: str):
    """Parses '9:20 AM', '09:20', etc. into minutes-since-midnight for sorting.
    Returns None if unparseable (kept as unsorted/appended)."""
    cleaned = time_str.strip().upper().replace(" ", "")
    for fmt in ("%I:%M%p", "%H:%M"):
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.hour * 60 + dt.minute
        except ValueError:
            continue
    return None


def extract_events_from_text(text: str) -> list:
    """Splits text into sentences and pairs any time mention in a sentence
    with that sentence as the event description."""
    if not text:
        return []
    events = []
    for sentence in SENTENCE_SPLIT.split(text.strip()):
        sentence = sentence.strip()
        if not sentence:
            continue
        time_match = PATTERNS["times"].search(sentence)
        if time_match:
            events.append({
                "time": time_match.group().strip(),
                "event": sentence,
                "_sort_key": _parse_time_to_minutes(time_match.group()),
                "_source": "description",
            })
    return events


def extract_events_from_evidence(evidence_records: list) -> list:
    """evidence_records: list of dicts as returned by evidence/storage.py's
    list_evidence_for_complaint(), each with extracted_entities_json."""
    import json
    events = []
    for record in evidence_records:
        entities = record.get("extracted_entities") or {}
        if isinstance(record.get("extracted_entities_json"), str):
            entities = json.loads(record["extracted_entities_json"] or "{}")
        times = entities.get("times", [])
        filename = record.get("filename", "evidence file")
        for t in times:
            events.append({
                "time": t,
                "event": f"Timestamp found in uploaded evidence: {filename}",
                "_sort_key": _parse_time_to_minutes(t),
                "_source": "evidence",
            })
    return events


def build_timeline(user_text: str, evidence_records: list = None) -> list:
    """Main entry point. Returns a list of {time, event} dicts, sorted
    chronologically where a time could be parsed, with unparseable-time
    events appended at the end in original order."""
    evidence_records = evidence_records or []
    all_events = extract_events_from_text(user_text) + extract_events_from_evidence(evidence_records)

    timed = [e for e in all_events if e["_sort_key"] is not None]
    untimed = [e for e in all_events if e["_sort_key"] is None]

    timed.sort(key=lambda e: e["_sort_key"])

    ordered = timed + untimed
    # de-duplicate identical (time, event) pairs that might appear from overlapping sources
    seen = set()
    result = []
    for e in ordered:
        key = (e["time"], e["event"])
        if key in seen:
            continue
        seen.add(key)
        result.append({"time": e["time"], "event": e["event"]})
    return result


if __name__ == "__main__":
    import json
    sample_text = (
        "I received a phishing SMS at 09:15 AM. I clicked the malicious link at 09:17 AM. "
        "I then entered my OTP around 09:20 AM. My money was debited at 09:21 AM."
    )
    timeline = build_timeline(sample_text)
    print(json.dumps(timeline, indent=2))
