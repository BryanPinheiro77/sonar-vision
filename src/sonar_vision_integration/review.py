"""Correlate admitted client receipts with an operator's private journal (#52).

Offline only. No endpoint, images, identity metrics or physical-risk inference.
"""

import argparse
from collections import Counter
from hashlib import sha256
import html
import json
import os
from pathlib import Path

from sonar_vision.benchmark import summarize


def read_lines(path, max_bytes=64 * 1024 * 1024):
    if path.stat().st_size > max_bytes:
        raise ValueError("report_too_large")
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if len(line) > 65536:
                raise ValueError("record_too_large")
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError("invalid_record")
            yield value


def correlate(receipts: Path, journals: list[Path]):
    rows = list(read_lines(receipts))
    if not rows or rows[0].get("kind") != "private_client_receipts":
        raise ValueError("invalid_receipts_header")
    predictions, configurations = {}, []
    for path in journals:
        stream = iter(read_lines(path))
        header = next(stream, {})
        if header.get("kind") != "private_prediction_journal":
            raise ValueError("invalid_journal_header")
        configurations.append(header["configuration"])
        for row in stream:
            message = row.get("message_id")
            if not isinstance(message, str) or message in predictions:
                raise ValueError("duplicate_or_missing_observation_id")
            predictions[message] = row
    frames = []
    for row in rows[1:]:
        event = {
            "frame_id": row.get("frame_id"),
            "outcome": row.get("outcome"),
            "source_frame_index": row.get("source_frame_index"),
            "jpeg_sha256": row.get("jpeg_sha256"),
            "reason": row.get("reason"),
            "latency_ms": row.get("latency_ms"),
            "objects": row.get("objects", []),
            "audio_admission": row.get("audio"),
            "audio_text": row.get("audio_text"),
            "diagnostic": None,
        }
        if row.get("outcome") == "accepted":
            pred = predictions.get(row.get("observation_id"))
            if pred is not None:
                if any(
                    pred.get(k) != row.get(k)
                    for k in (
                        "frame_id",
                        "captured_at_ms",
                        "tracker_epoch",
                        "jpeg_sha256",
                    )
                ):
                    raise ValueError("capture_correlation_mismatch")
                event["diagnostic"] = pred
        frames.append(event)
    latencies = [
        x["latency_ms"] for x in frames if isinstance(x["latency_ms"], (int, float))
    ]
    return {
        "kind": "private_remote_review",
        "source": rows[0],
        "receipts_sha256": sha256(receipts.read_bytes()).hexdigest(),
        "configurations": configurations,
        "frames": frames,
        "outcomes": dict(Counter(x["outcome"] for x in frames)),
        "latency": summarize(latencies) if latencies else None,
        "accepted_without_diagnostic": sum(
            x["outcome"] == "accepted" and x["diagnostic"] is None for x in frames
        ),
        "limitations": [
            "Association to predictions is not tracking accuracy or physical risk",
            "Client local orientation/urgency are simulated; camera motion remains unknown",
            "No diagnostics for rejected client responses are displayed as admitted",
        ],
    }


def render(report):
    parts = [
        '<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Avaliação remota</title>',
        "<style>body{font:16px system-ui;line-height:1.5;margin:24px}table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:8px;vertical-align:top}</style>",
        "<h1>Resultados do cliente remoto</h1><p>Orientação/urgência simuladas. Trajetória de câmera móvel permanece desconhecida. Sem reprodução física de áudio ou inferência de risco.</p>",
        "<p>As caixas são do diagnóstico privado do servidor, correlacionadas por observação/captura. Ausência de caixa pode significar diagnóstico perdido/desligado, não ausência de objeto.</p>",
        "<table><tr><th>Frame</th><th>Admissão/descarte</th><th>Latência</th><th>Objetos, IDs e escadas</th><th>Diagnóstico de caixas</th><th>Sugestão</th></tr>",
    ]

    def escape(value):
        return html.escape(str(value))

    for frame in report["frames"]:
        objects = "<br>".join(
            escape(
                f"{x['class_name']} | id={x['track_id']} | score={x['confidence']:.3f} | stairs={x['stair_direction']} | motion={x['movement']}"
            )
            for x in frame["objects"]
        )
        diag = frame["diagnostic"]
        boxes = (
            "<br>".join(
                escape(f"{x['class_name']} id={x['track_id']} box={x['box']}")
                for x in diag["detections"]
            )
            if diag is not None
            else "indisponível"
        )
        if frame.get("overlay"):
            boxes += (
                '<br><img width="320" alt="Previsões do servidor" src="'
                + html.escape(frame["overlay"], quote=True)
                + '">'
            )
        parts.append(
            "<tr>"
            + "".join(
                "<td>" + v + "</td>"
                for v in (
                    escape(frame["frame_id"]),
                    escape(frame["reason"] or frame["outcome"]),
                    escape(frame["latency_ms"]),
                    objects,
                    boxes,
                    escape(frame["audio_text"] or frame["audio_admission"]),
                )
            )
            + "</tr>"
        )
    return "\n".join(parts) + "</table></html>"


def add_overlays(report, video: Path, directory: Path):
    """Explicit local reconstruction, verified against the uploaded JPEG hash."""
    from sonar_vision_api.runtime_options import file_hash

    if file_hash(video) != report["source"].get("video_sha256"):
        raise ValueError("video_hash_mismatch")
    import cv2

    directory.mkdir(mode=0o700)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError("video_unreadable")
        for number, frame in enumerate(report["frames"]):
            if frame["diagnostic"] is None:
                continue
            index = frame["source_frame_index"]
            if (
                type(index) is not int
                or index < 0
                or not capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ):
                raise ValueError("source_frame_unavailable")
            ok, image = capture.read()
            if not ok:
                raise ValueError("source_frame_unavailable")
            edge = report["source"].get("upload_max_edge")
            if edge is not None:
                ratio = min(1, edge / max(image.shape[:2]))
                if ratio < 1:
                    image = cv2.resize(
                        image,
                        (
                            max(1, round(image.shape[1] * ratio)),
                            max(1, round(image.shape[0] * ratio)),
                        ),
                        interpolation=cv2.INTER_AREA,
                    )
            quality = report["source"].get("upload_jpeg_quality", 95)
            if type(quality) is not int or not 1 <= quality <= 100:
                raise ValueError("invalid_upload_jpeg_quality")
            ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
            if not ok or sha256(jpeg.tobytes()).hexdigest() != frame["jpeg_sha256"]:
                raise ValueError("reconstructed_capture_hash_mismatch")
            image = cv2.imdecode(jpeg, cv2.IMREAD_COLOR)
            height, width = image.shape[:2]
            for obj in frame["diagnostic"]["detections"]:
                x1, y1, x2, y2 = obj["box"]
                cv2.rectangle(
                    image,
                    (round(x1 * width), round(y1 * height)),
                    (round(x2 * width), round(y2 * height)),
                    (0, 220, 0),
                    2,
                )
                label = f"{obj['class_name']} id={obj['track_id']} {obj['confidence']:.2f} {obj['stair_direction'] or ''}"
                cv2.putText(
                    image,
                    label,
                    (round(x1 * width), max(15, round(y1 * height) - 5)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 220, 0),
                    1,
                )
            ok, output = cv2.imencode(".jpg", image)
            if not ok:
                raise ValueError("overlay_encode_failed")
            path = directory / f"frame-{number}.jpg"
            with os.fdopen(
                os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
            ) as stream:
                stream.write(output.tobytes())
            frame["overlay"] = directory.name + "/" + path.name
    finally:
        capture.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--journal", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--video",
        type=Path,
        help="explicit private local overlays, no second inference",
    )
    args = parser.parse_args()
    report = correlate(args.receipts, args.journal)
    if args.output.exists():
        parser.error("output must be new")
    if args.video:
        add_overlays(
            report, args.video, args.output.with_name(args.output.stem + "-images")
        )
    with os.fdopen(
        os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
    ) as stream:
        stream.write(render(report))
    print(
        json.dumps(
            {
                "outcomes": report["outcomes"],
                "accepted_without_diagnostic": report["accepted_without_diagnostic"],
            }
        )
    )


if __name__ == "__main__":
    main()
