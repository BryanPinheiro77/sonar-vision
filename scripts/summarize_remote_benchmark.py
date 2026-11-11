"""#22 publishable aggregates from a private external-load report and server logs.

No provisioning. Never exports credentials, endpoint, device/session/frame IDs or
local paths. Server resources exclude warmup using only the server's timestamps;
client and server clocks are never subtracted. See docs/experiments/issue-22-reproduce.md.
"""
import argparse
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
import statistics

from sonar_vision_integration.remote_load import attach_server_log


def public_summary(report_path, log_path, *, timestamps=None, resources=None, container_inspect=None):
    report = json.loads(Path(report_path).read_text())
    attach_server_log(report, Path(log_path))
    configuration = report['configuration']
    # Corpus metadata is projected explicitly: future/private annotations must not
    # become public merely because a producer added a field to its raw report.
    corpus = [{key: item[key] for key in ('jpeg_sha256', 'bytes', 'height_width')}
              for item in configuration['corpus']]
    result = {
        'kind': 'external_benchmark_public_aggregate',
        'acceptance_evaluated': False,
        'configuration': {key: configuration[key] for key in (
            'devices', 'offered_fps_per_device', 'offering_duration_s',
            'warmup_s_per_device', 'phase', 'queue')},
        'measurement_continuity': report['measurement_continuity'],
        'opportunities': report['opportunity_counts'],
        'outcomes': report['attempt_outcomes'],
        'devices': [{key: device[key] for key in (
            'offered_fps', 'offering_duration_s', 'wall_s_including_drain',
            'admitted_within_offering_window', 'admitted_fps_within_offering_window',
            'attempt_failure_fraction', 'synthetic_capture_to_admission',
            'https_call_to_admission')} for device in report['devices']],
        'server': report['server_observations'],
        'resources': None,
        'private_report_sha256': sha256(Path(report_path).read_bytes()).hexdigest(),
        'limitations': ['Preencoded JPEG does not measure physical capture/encoding',
                        'HTTPS duration is not pure network RTT',
                        'Synthetic outcomes do not validate tracking or tactile hardware'],
    }
    result['configuration']['scheduling'] = configuration.get('scheduling', 'periodic')
    result['configuration']['offered_rate_is_start_ceiling'] = configuration.get('offered_rate_is_start_ceiling', False)
    result['configuration']['corpus'] = corpus
    if (timestamps is None) != (resources is None):
        raise ValueError('timestamps and resources must be supplied together')
    if resources is not None:
        if container_inspect is None:
            raise ValueError('container inspect required for resource identity')
        expected = {(device['device'], row['session_id'], row['frame_id'])
                    for device in report['devices'] for row in device['rows']}
        events = {}
        for line in Path(timestamps).read_text().splitlines():
            try:
                timestamp, payload = line.split(' ', 1)
                event = json.loads(payload)
            except ValueError:
                continue
            if not isinstance(event, dict) or event.get('event') != 'inference_request':
                continue
            key = (event.get('device_id'), event.get('session_id'), event.get('frame_id'))
            if key not in expected:
                continue
            if key in events:
                raise ValueError('duplicate timestamped server request')
            duration = event.get('total_ms')
            if type(duration) not in (int, float) or not 0 <= duration < 60000:
                raise ValueError('invalid server duration')
            events[key] = (datetime.fromisoformat(timestamp.replace('Z', '+00:00')), duration)
        plain_keys = set()
        for line in Path(log_path).read_text().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if isinstance(event, dict) and event.get('event') == 'inference_request':
                key = (event.get('device_id'), event.get('session_id'), event.get('frame_id'))
                if key in expected:
                    plain_keys.add(key)
        if set(events) != plain_keys or not events:
            raise ValueError('timestamped and plain logs must contain the same measured requests')
        lower = min(end - timedelta(milliseconds=duration) for end, duration in events.values())
        upper = max(end for end, _ in events.values())
        samples = [json.loads(line) for line in Path(resources).read_text().splitlines()]
        if not samples or not all(isinstance(sample, dict) for sample in samples):
            raise ValueError('nonempty resource records required')
        header = samples[0]
        if header.get('kind') != 'server_container_resource_samples':
            raise ValueError('resource header required')
        inspected = json.loads(Path(container_inspect).read_text())
        if not isinstance(inspected, list) or len(inspected) != 1 or not isinstance(inspected[0], dict):
            raise ValueError('one container inspect record required')
        identity = inspected[0]
        limits = identity['HostConfig']
        if (header['container_id'] != identity['Id'] or header['image_id'] != identity['Image']
                or header['cpu_limit'] != (limits.get('NanoCpus', 0) / 1e9 or None)
                or header['memory_limit_bytes'] != limits.get('Memory', 0)):
            raise ValueError('resource identity or limits mismatch')
        selected = [sample for sample in samples[1:] if 'sampled_at_utc' in sample and
                    lower <= datetime.fromisoformat(sample['sampled_at_utc']) -
                    timedelta(seconds=sample['collector_duration_s']) and
                    datetime.fromisoformat(sample['sampled_at_utc']) <= upper]
        cpu = [s['cpu_percent_capacity'] for s in selected if s['cpu_percent_capacity'] is not None]
        result['resources'] = {
            'scope': 'server resource samples wholly inside server measured-request window; warmup excluded',
            'cpu_limit': header['cpu_limit'],
            'memory_limit_bytes': header['memory_limit_bytes'],
            'image_id': header['image_id'],
            'samples': len(selected),
            'mean_cpu_percent_capacity': statistics.mean(cpu) if cpu else None,
            'max_cpu_percent_capacity': max(cpu, default=None),
            'max_memory_used_bytes': max((s['memory_used_bytes'] for s in selected), default=None),
            'max_ram_percent_container_limit': max((s['ram_percent_capacity'] for s in selected
                if s['ram_percent_capacity'] is not None), default=None),
            'memory_is_docker_usage_excluding_cache_not_rss': True,
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--server-log', type=Path, required=True)
    parser.add_argument('--server-timestamps', type=Path)
    parser.add_argument('--resources', type=Path)
    parser.add_argument('--container-inspect', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = public_summary(args.report, args.server_log,
            timestamps=args.server_timestamps, resources=args.resources,
            container_inspect=args.container_inspect)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
            stream.write('\n')
    except (ValueError, OSError, KeyError, TypeError):
        parser.exit(2, 'aggregation failed; inspect private reports/logs and use a new output file\n')
    print('Public aggregate created; no cloud resources changed.')


if __name__ == '__main__':
    main()
