"""Replay one authorized local video into private paired #11 evaluation inputs."""

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
from pickle import UnpicklingError
import sys
from time import perf_counter

from .core import Frame, VisionService
from .evaluation import MAX_INPUT, canonical, frame_from_result, load_input, require
from .evaluate_motion import _private_output, motion_frame_from_result, validate_motion
from .trajectory import TrajectoryConfig


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def validate_templates(snapshot, motion):
    clips = validate_motion(snapshot, motion)
    require(len(clips) == 1, 'single_clip_required')
    require(snapshot['run']['latency_scope'] == 'processing'
            and snapshot['run']['model_load_included'] is False, 'processing_scope_required')
    require(all(f['status'] == 'ok' and not f['predictions'] for f in snapshot['frames'])
            and all(not f['predictions'] for f in motion['frames']), 'annotation_only_templates')
    return next(iter(clips.values()))


def replay(snapshot, motion, capture, factory):
    """Decode a single sequence; caller verifies source/weights before this call.

    The decoder owns original frame ordering; supplied reviewed PTS owns time.
    No seek, FPS interpolation, automatic labels or fixed-camera assumption.
    """
    service = None
    try:
        clip = validate_templates(snapshot, motion)
        config = TrajectoryConfig(**motion['trajectory_config'])
        output, sidecar = deepcopy(snapshot), deepcopy(motion)
        service = VisionService(factory, trajectory_config=config)
        index, started = -1, perf_counter()
        require(capture.isOpened(), 'source_not_open')
        service.open('offline-evaluation', 'replay')
        for base, labels in zip(output['frames'], sidecar['frames']):
            while index < base['frame_index']:
                ok, image = capture.read()
                require(ok and image is not None, 'source_ended_before_annotation')
                index += 1
                require(tuple(image.shape[:2]) == (clip['height'], clip['width']),
                        'source_dimensions')
            result = service.process(Frame('offline-evaluation', 'replay', str(index),
                                           labels['captured_at_ms'], image,
                                           camera_motion=labels['camera_motion']))
            frame = frame_from_result(clip['clip_id'], index, result,
                                      base['ground_truth'], latency_ms=result.processing_ms)
            paired = motion_frame_from_result(frame, result,
                                              camera_motion=labels['camera_motion'],
                                              references=labels['references'])
            base.clear()
            base.update(frame)
            labels.clear()
            labels.update(paired)
        output['run']['elapsed_ms'] = (perf_counter() - started) * 1000
    finally:
        try:
            capture.release()
        finally:
            if service is not None:
                service.close('offline-evaluation', 'replay')
    sidecar['snapshot_sha256'] = hashlib.sha256(canonical(output)).hexdigest()
    validate_motion(output, sidecar)
    return output, sidecar


def write_bundle(path, snapshot, motion, provenance):
    target = _private_output(path)
    require(not target.exists(), 'output_exists')
    serialized = {name: (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)
                         + '\n').encode('utf-8')
                  for name, data in (('snapshot.json', snapshot), ('motion.json', motion),
                                     ('provenance.json', provenance))}
    require(all(len(data) <= MAX_INPUT for data in serialized.values()), 'output_too_large')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.mkdir(mode=0o700)
    # Exclusive directory creation prevents reusing a partial previous run.
    for name, data in serialized.items():
        with os.fdopen(os.open(target / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                       'wb') as stream:
            stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'motion', 'video', 'weights', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--stair-weights', type=Path)
    parser.add_argument('--stair-sha256')
    args = parser.parse_args(argv)
    try:
        snapshot, motion = load_input(args.snapshot), load_input(args.motion)
        clip = validate_templates(snapshot, motion)
        require(bool(args.stair_weights) == bool(args.stair_sha256), 'specialist_hash_required')
        target = _private_output(args.output)
        require(not target.exists(), 'output_exists')
        video_hash, weights_hash = file_hash(args.video), file_hash(args.weights)
        require(clip['kind'] == 'recorded' and clip['sha256'] == video_hash, 'video_hash')
        require(snapshot['run']['model']['sha256'] == weights_hash, 'weights_hash')
        if args.stair_weights:
            require(file_hash(args.stair_weights) == args.stair_sha256, 'specialist_hash')
        import cv2
        from .ultralytics_backend import UltralyticsFactory, VisionConfig

        settings = snapshot['run']['configuration']
        factory = UltralyticsFactory(args.weights, VisionConfig(
            confidence=settings['detector_confidence'], image_size=settings['image_size'],
            device=settings['device']), stair_direction_weights=args.stair_weights)
        require(settings['tracker_version'] == 'ByteTrack-' + factory.metadata['packages']['ultralytics'],
                'tracker_version_mismatch')
        # Disposable warmup never contributes tracker history or quality samples.
        factory.warmup()
        try:
            snapshot, motion = replay(snapshot, motion, cv2.VideoCapture(str(args.video)), factory)
        except cv2.error as error:
            raise ValueError('decoder_failure') from error
        provenance = {
            'schema_version': 1, 'video_sha256': video_hash,
            'models': factory.metadata, 'trajectory_config': asdict(TrajectoryConfig(**motion['trajectory_config'])),
            'snapshot_sha256': motion['snapshot_sha256'],
            'timestamp_basis': 'operator_supplied_reviewed_presentation_timestamps',
            'image_transform': 'original_decoded_bgr_no_upload_jpeg',
            'acceptance_evaluated': False,
            'limitations': ['Selected frames only; annotation and permissions require human review',
                            'No network/ESP capture/audio/tactile validation',
                            'Elapsed replay includes decoding; processing samples exclude it',
                            'Decode failure aborts; no end-to-end quality report is emitted'],
        }
        write_bundle(target, snapshot, motion, provenance)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, RecursionError, EOFError, UnpicklingError):
        print('motion replay failed; inspect private inputs, models and output location', file=sys.stderr)
        return 2
    print(json.dumps({'frames': len(snapshot['frames']), 'acceptance_evaluated': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
