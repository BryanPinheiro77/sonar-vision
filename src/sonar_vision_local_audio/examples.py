"""Check the documented examples: `python -m sonar_vision_local_audio.examples FILE`.

Runs every catalog case and scenario of docs/protocol/exemplos-audio-local.json
against the reference model and exits 1 if any expected outcome differs.
"""

import argparse
import copy
import json
from pathlib import Path
import sys

from .arbiter import Arbiter, Suggestion
from .catalog import install

AUDIO_FIELDS = {"version", "type", "session_id", "message_id", "frame_id", "captured_at_ms",
                "valid_for_ms", "observation_id", "text", "directional"}


def _no_duplicates(pairs):
    keys = [key for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate JSON key")
    return dict(pairs)


def load(path) -> dict:
    with open(path, encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_no_duplicates)


def to_suggestion(message: dict) -> Suggestion:
    """Envelope checks of contract 0.1 (unchanged by #25) before arbitration."""
    if set(message) != AUDIO_FIELDS or message["version"] != "0.1" \
            or message["type"] != "audio_suggestion":
        raise ValueError("not a contract 0.1 audio_suggestion")
    if type(message["directional"]) is not bool or type(message["captured_at_ms"]) is not int \
            or type(message["valid_for_ms"]) is not int or message["valid_for_ms"] <= 0:
        raise ValueError("invalid audio_suggestion types")
    return Suggestion(message["message_id"], message["session_id"], message["frame_id"],
                      message["captured_at_ms"], message["valid_for_ms"], message["text"],
                      message["directional"])


def _apply(manifest: dict, files: dict, change: dict):
    op = change["op"]
    if op == "set":
        manifest[change["field"]] = change["value"]
    elif op == "remove_entry":
        manifest["entries"] = [e for e in manifest["entries"] if e["id"] != change["id"]]
    elif op == "set_entry":
        for entry in manifest["entries"]:
            if entry["id"] == change["id"]:
                entry[change["field"]] = change["value"]
    elif op == "duplicate_entry":
        manifest["entries"].append(copy.deepcopy(
            next(e for e in manifest["entries"] if e["id"] == change["id"])))
    elif op == "remove_file":
        files.pop(change["path"])
    elif op == "replace_file":
        files[change["path"]] = change["content"].encode("utf-8")
    else:
        raise ValueError(f"unknown change op {op}")


def build(doc: dict, changes=()):
    manifest = copy.deepcopy(doc["catalog"])
    files = {path: content.encode("utf-8") for path, content in doc["files"].items()}
    for change in changes:
        _apply(manifest, files, change)
    return manifest, files


def run(doc: dict) -> list[str]:
    failures = []
    profile = doc["device_profile"]
    base, status = install(None, *build(doc), profile)
    if status != "installed":
        return [f"base catalog: {status}"]
    for case in doc["catalog_cases"]:
        catalog, status = install(base, *build(doc, case["changes"]), profile)
        # A rejected candidate must leave the working catalog in place.
        if status != case["expected"] or (status != "installed" and catalog is not base):
            failures.append(f"catalog {case['name']}: got {status}, expected {case['expected']}")
    for scenario in doc["scenarios"]:
        catalog = None if scenario.get("catalog") == "none" else base
        orientation = {int(k): v for k, v in scenario.get("orientation", {}).items()}
        arbiter = Arbiter(catalog, scenario.get("session_id", "boot-demo-a"),
                          {k: v for k, v in scenario.get("captures", {}).items()},
                          lambda captured, table=orientation: table.get(captured, 0.0))
        try:
            for step in scenario["steps"]:
                at, op = step["at"], step["op"]
                if op == "suggestion":
                    arbiter.suggestion(at, to_suggestion(step["message"]))
                elif op == "urgency":
                    arbiter.urgency(at, step["active"])
                elif op == "availability":
                    arbiter.availability(at, step["state"])
                elif op == "orientation":
                    # Rotation since that capture as seen at this time; null = invalid.
                    orientation[step["captured_at_ms"]] = step["deg"]
                elif op in ("tick", "finished"):
                    getattr(arbiter, op)(at)
                else:
                    raise ValueError(f"unknown step op {op}")
        except ValueError as error:
            got = [["error", str(error)]]
        else:
            got = [list(event) for event in arbiter.log]
        if got != scenario["expected"]:
            failures.append(f"scenario {scenario['name']}: got {got}, expected {scenario['expected']}")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    doc = load(args.file)
    failures = run(doc)
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"catalog_cases={len(doc['catalog_cases'])} scenarios={len(doc['scenarios'])} "
          f"failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
