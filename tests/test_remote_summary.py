"""#22 aggregations exclude warmup and private identifiers; reject mixed containers."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


class SummaryTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('remote_summary',
            Path(__file__).resolve().parents[1] / 'scripts/summarize_remote_benchmark.py')
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.root = Path(self.enterContext(TemporaryDirectory()))
        self.report = self.root / 'report.json'
        self.log = self.root / 'server.log'
        self.times = self.root / 'timestamps.log'
        self.resources = self.root / 'resources.jsonl'
        self.inspect = self.root / 'inspect.json'
        config = dict(devices=1, offered_fps_per_device=10, offering_duration_s=1,
                      warmup_s_per_device=30, phase='aligned', corpus=[dict(jpeg_sha256='a'*64,
                          bytes=100, height_width=[8,8], private_path='PRIVATE-ANNOTATION')], queue=False,
                      source_id='PRIVATE-SOURCE')
        device = dict(device='PRIVATE-DEVICE', rows=[dict(session_id='PRIVATE-SESSION', frame_id=str(i))
            for i in (1, 2)], offered_fps=10, offering_duration_s=1,
            wall_s_including_drain=1, admitted_within_offering_window=2,
            admitted_fps_within_offering_window=2, attempt_failure_fraction=0,
            synthetic_capture_to_admission={}, https_call_to_admission={})
        self.report.write_text(json.dumps(dict(configuration=config, devices=[device],
            measurement_continuity={'continuous': True}, opportunity_counts={}, attempt_outcomes={},
            private_token='PRIVATE-TOKEN', endpoint='https://PRIVATE-ENDPOINT')))
        self.events = [dict(event='inference_request', device_id='PRIVATE-DEVICE',
            session_id='PRIVATE-SESSION', frame_id=str(i), status=200, total_ms=100,
            inference_ms=70) for i in (1, 2)]
        self.log.write_text('\n'.join(map(json.dumps, self.events)))
        self.times.write_text('\n'.join(f'2026-10-08T00:00:{sec:02d}Z '+json.dumps(event)
            for sec, event in zip((10, 12), self.events)))
        self.header = dict(kind='server_container_resource_samples', container_id='c'*64,
            image_id='sha256:'+'a'*64, cpu_limit=4, memory_limit_bytes=300)
        self.inspect.write_text(json.dumps([dict(Id='c'*64, Image=self.header['image_id'],
            HostConfig=dict(NanoCpus=4*10**9, Memory=300))]))
        warm = dict(sampled_at_utc='2026-10-08T00:00:09Z', collector_duration_s=.1,
                    cpu_percent_capacity=100, memory_used_bytes=290, ram_percent_capacity=96)
        measured = dict(warm, sampled_at_utc='2026-10-08T00:00:11Z',
                        cpu_percent_capacity=25, memory_used_bytes=100, ram_percent_capacity=33)
        self.resources.write_text('\n'.join(map(json.dumps,[self.header, warm, measured])))

    def summarize(self):
        return self.module.public_summary(self.report, self.log, timestamps=self.times,
            resources=self.resources, container_inspect=self.inspect)

    def test_warmup_excluded_and_identifiers_not_exported(self):
        result = self.summarize()
        self.assertEqual(result['resources']['samples'], 1)
        self.assertEqual(result['resources']['mean_cpu_percent_capacity'], 25)
        self.assertEqual(result['resources']['max_memory_used_bytes'], 100)
        self.assertEqual(result['server']['matched'], 2)
        self.assertEqual(result['server']['stages']['inference_ms']['p95_ms'], 70)
        for secret in ('PRIVATE-DEVICE', 'PRIVATE-SESSION', 'PRIVATE-SOURCE', 'PRIVATE-TOKEN',
                       'PRIVATE-ENDPOINT', 'PRIVATE-ANNOTATION', str(self.root)):
            self.assertNotIn(secret, json.dumps(result))

    def test_different_container_is_not_accepted_as_resource_evidence(self):
        value = json.loads(self.inspect.read_text())
        value[0]['Id'] = 'd'*64
        self.inspect.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'identity'):
            self.summarize()

    def test_same_count_of_different_timestamped_requests_is_rejected(self):
        other = dict(self.events[1], frame_id='3')
        report = json.loads(self.report.read_text())
        report['devices'][0]['rows'].append(dict(session_id='PRIVATE-SESSION', frame_id='3'))
        self.report.write_text(json.dumps(report))
        self.times.write_text('2026-10-08T00:00:10Z '+json.dumps(self.events[0])+'\n'
                             +'2026-10-08T00:00:12Z '+json.dumps(other))
        with self.assertRaisesRegex(ValueError, 'same measured'):
            self.summarize()

    def test_empty_or_truncated_exports_have_controlled_errors(self):
        self.resources.write_text('')
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            self.summarize()
        self.resources.write_text(json.dumps(self.header))
        self.inspect.write_text('[]')
        with self.assertRaisesRegex(ValueError, 'one container'):
            self.summarize()
