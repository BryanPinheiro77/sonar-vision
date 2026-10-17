"""Actual VisionService/estimator replay with scripted images; no accuracy claim."""
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import asdict
import hashlib
import io
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sonar_vision.core import Detection
from sonar_vision.evaluation import canonical, load_input
from sonar_vision.evaluate_motion import evaluate
from sonar_vision.replay_motion import file_hash, main, replay, validate_templates, write_bundle
from sonar_vision.trajectory import TrajectoryConfig

ROOT = Path(__file__).resolve().parents[1]


def templates(camera='fixed'):
    data = load_input(ROOT / 'docs/experiments/issue-33-fixture.json')
    clip = data['dataset_manifest']['clips'][0]
    data['dataset_manifest']['clips'] = [clip]
    data['run']['latency_scope'] = 'processing'
    truth = {'reference_id': 'ref1', 'class_name': 'person', 'box': [.1, .1, .6, .9],
             'visible': True, 'stair_direction': None}
    data['frames'] = [dict(clip_id=clip['clip_id'], frame_index=index, tracker_epoch='template',
                           status='ok', latency_ms=0, ground_truth=[deepcopy(truth)], predictions=[])
                      for index in (0, 2, 5, 9, 10, 14, 15, 17, 20, 24)]
    motion = {'schema_version': 1, 'snapshot_sha256': hashlib.sha256(canonical(data)).hexdigest(),
              'trajectory_config': asdict(TrajectoryConfig()),
              'frames': [dict(clip_id=f['clip_id'], frame_index=f['frame_index'],
                              captured_at_ms=100*i + (i % 2)*7, camera_motion=camera,
                              references=[dict(reference_id='ref1', segment_id='seg1',
                                               movement='stable', lateral_direction=None)],
                              predictions=[]) for i, f in enumerate(data['frames'])]}
    return data, motion


class Image:
    shape = (480, 640, 3)


class Capture:
    def __init__(self, count=25):
        self.count, self.reads, self.released = count, 0, False
    def isOpened(self):
        return True
    def read(self):
        self.reads += 1
        return (True, Image()) if self.reads <= self.count else (False, None)
    def release(self):
        self.released = True


class Backend:
    def __init__(self):
        self.calls, self.closed = 0, False
    def infer(self, image):
        self.calls += 1
        return [Detection('person', .9, (.1, .1, .6, .9), '1')]
    def close(self):
        self.closed = True


class MotionReplayTests(unittest.TestCase):
    def test_service_to_evaluator_preserves_original_alignment_and_truth(self):
        snapshot, motion = templates()
        before = deepcopy((snapshot, motion))
        capture, backend = Capture(), Backend()
        output, paired = replay(snapshot, motion, capture, lambda: backend)
        self.assertEqual((snapshot, motion), before)
        self.assertEqual(backend.calls, 10)
        self.assertEqual(capture.reads, 25)
        self.assertTrue(capture.released and backend.closed)
        self.assertEqual([f['frame_index'] for f in output['frames']],
                         [f['frame_index'] for f in snapshot['frames']])
        self.assertEqual([f['captured_at_ms'] for f in paired['frames']],
                         [f['captured_at_ms'] for f in motion['frames']])
        self.assertEqual([f['ground_truth'] for f in output['frames']],
                         [f['ground_truth'] for f in snapshot['frames']])
        self.assertEqual(paired['snapshot_sha256'], hashlib.sha256(canonical(output)).hexdigest())
        report, _ = evaluate(output, paired)
        self.assertEqual(report['overall']['known_truth'], 10)
        self.assertGreater(report['overall']['correct'], 0)
        self.assertFalse(report['acceptance_evaluated'])

    def test_camera_context_does_not_become_fixed(self):
        for camera in ('moving', 'unknown'):
            with self.subTest(camera=camera):
                a, b = templates(camera)
                a, b = replay(a, b, Capture(), Backend)
                report, _ = evaluate(a, b)
                self.assertEqual(report['overall']['abstentions'], 10)
                self.assertEqual(report['camera_guard_violations'], 0)

    def test_eof_dimensions_and_inference_failures_release_resources(self):
        for case in ('eof', 'dimensions', 'infer'):
            a, b = templates()
            capture, backend = Capture(3 if case == 'eof' else 25), Backend()
            if case == 'dimensions':
                a['dataset_manifest']['clips'][0]['width'] = 123
                b['snapshot_sha256'] = hashlib.sha256(canonical(a)).hexdigest()
            if case == 'infer':
                backend.infer = lambda image: (_ for _ in ()).throw(RuntimeError('failed'))
            with self.subTest(case=case), self.assertRaises((ValueError, RuntimeError)):
                replay(a, b, capture, lambda: backend)
            self.assertTrue(capture.released and backend.closed)

    def test_prediction_or_nonprocessing_templates_rejected(self):
        for change in ('predictions', 'scope', 'timestamp'):
            a, b = templates()
            if change == 'predictions':
                a['frames'][0]['predictions'] = [dict(track_id='1',class_name='person',
                    box=[.1,.1,.6,.9],confidence=.9,stair_direction=None)]
                b['frames'][0]['predictions'] = [dict(movement='unknown',reason='insufficient_history',
                                                      lateral_direction=None)]
            elif change == 'scope':
                a['run']['latency_scope'] = 'capture_to_response'
            else:
                b['frames'][1]['captured_at_ms'] = 0
            b['snapshot_sha256'] = hashlib.sha256(canonical(a)).hexdigest()
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_templates(a, b)

    def test_stair_direction_survives_export_without_invented_track(self):
        a, b = templates()
        a['dataset_manifest']['clips'][0]['classes'] = ['stairs']
        for f in a['frames']:
            f['ground_truth'][0].update(class_name='stairs', stair_direction='up')
        b['snapshot_sha256'] = hashlib.sha256(canonical(a)).hexdigest()
        backend = Backend()
        backend.infer = lambda image: [Detection('stairs', .9, (.1,.1,.6,.9), stair_direction='up')]
        a, b = replay(a, b, Capture(), lambda: backend)
        self.assertEqual(a['frames'][0]['predictions'][0]['stair_direction'], 'up')
        self.assertIsNone(a['frames'][0]['predictions'][0]['track_id'])
        self.assertEqual(b['frames'][0]['predictions'][0]['reason'], 'no_track')

    def test_private_bundle_no_overwrite_or_external_path(self):
        with TemporaryDirectory() as directory, patch('pathlib.Path.cwd', return_value=Path(directory)):
            root = Path(directory)
            target = root / 'results' / 'replay01'
            with patch('sonar_vision.replay_motion.MAX_INPUT', 1), self.assertRaises(ValueError):
                write_bundle(target, {}, {}, {})
            self.assertFalse(target.exists())
            write_bundle(target, {}, {}, {})
            self.assertEqual({p.name for p in target.iterdir()},
                             {'snapshot.json', 'motion.json', 'provenance.json'})
            if os.name == 'posix':
                self.assertEqual(target.stat().st_mode & 0o777, 0o700)
                self.assertEqual((target/'motion.json').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                write_bundle(target, {}, {}, {})
            with self.assertRaises(ValueError):
                write_bundle(root/'public', {}, {}, {})
            (root/'results'/'outside').symlink_to(root, target_is_directory=True)
            with self.assertRaises(ValueError):
                write_bundle(root/'results'/'outside'/'escape', {}, {}, {})

    def test_invalid_template_releases_decoder_without_opening_backend(self):
        a, b = templates()
        b['snapshot_sha256'] = 'bad'
        capture = Capture()
        with self.assertRaises(ValueError):
            replay(a, b, capture, Backend)
        self.assertTrue(capture.released)

    def test_cli_validates_hashes_before_loading_models_and_writes_private_pair(self):
        with TemporaryDirectory() as directory, patch('pathlib.Path.cwd', return_value=Path(directory)):
            root = Path(directory)
            video, weights = root/'private-video.mp4', root/'model.pt'
            video.write_bytes(b'unit fixture, mocked decoding only')
            weights.write_bytes(b'unit fixture, mocked inference only')
            a, b = templates()
            clip = a['dataset_manifest']['clips'][0]
            clip.update(kind='recorded', stage='exploratory', split='exploration',
                        recorded_on='2026-10-17', camera='fixture-camera', sha256=file_hash(video),
                        permission_reference='fixture-permission',ethics_reference='fixture-ethics',
                        annotation_reference='fixture-annotation')
            a['run']['model']['sha256'] = file_hash(weights)
            a['run']['configuration']['tracker_version'] = 'ByteTrack-8.4.137'
            b['snapshot_sha256'] = hashlib.sha256(canonical(a)).hexdigest()
            snap, mot = root/'annotations.json', root/'motion.json'
            snap.write_text(json.dumps(a))
            mot.write_text(json.dumps(b))
            args = ['--snapshot',str(snap),'--motion',str(mot),'--video',str(video),
                    '--weights',str(weights),'--output',str(root/'results'/'replay')]
            backend = Backend()
            factory = SimpleNamespace(metadata={'packages':{'ultralytics':'8.4.137'}}, warmup=lambda:None)
            class Factory:
                metadata = factory.metadata
                warmup = staticmethod(factory.warmup)
                def __call__(self):
                    return backend
            with patch.dict('sys.modules', {'cv2': SimpleNamespace(VideoCapture=lambda _:Capture(), error=RuntimeError)}), \
                 patch('sonar_vision.ultralytics_backend.UltralyticsFactory', return_value=Factory()) as loader, \
                 redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                weights.write_bytes(b'changed model')
                self.assertEqual(main(args), 2)
                loader.assert_not_called()
                self.assertNotIn('private-video', stderr.getvalue())
                weights.write_bytes(b'unit fixture, mocked inference only')
                self.assertEqual(main(args), 0)
                self.assertNotIn('private-video', stdout.getvalue())
            report, _ = evaluate(load_input(root/'results/replay/snapshot.json'),
                                 load_input(root/'results/replay/motion.json'))
            self.assertEqual(report['overall']['known_truth'], 10)
            provenance = load_input(root/'results/replay/provenance.json')
            self.assertFalse(provenance['acceptance_evaluated'])

    @unittest.skipUnless(os.environ.get('SONAR_E2E_WEIGHTS'), 'trusted general weights required')
    def test_real_general_backend_and_opencv_decode_synthetic_video(self):
        import cv2
        import numpy as np
        from sonar_vision.ultralytics_backend import UltralyticsFactory

        a, b = templates('unknown')
        with TemporaryDirectory() as directory:
            video = Path(directory)/'synthetic.avi'
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*'MJPG'), 25, (640,480))
            self.assertTrue(writer.isOpened())
            try:
                for _ in range(25):
                    writer.write(np.zeros((480,640,3),dtype=np.uint8))
            finally:
                writer.release()
            factory = UltralyticsFactory(os.environ['SONAR_E2E_WEIGHTS'])
            factory.warmup()
            a, b = replay(a, b, cv2.VideoCapture(str(video)), factory)
            self.assertEqual(len(a['frames']), 10)
            self.assertEqual(a['dataset_manifest']['clips'][0]['kind'], 'synthetic')
            report, _ = evaluate(a, b)
            self.assertFalse(report['acceptance_evaluated'])
