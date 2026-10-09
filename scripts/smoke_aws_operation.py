"""#23 operational smoke on local Docker; no AWS calls/resources.

Builds two simulated images (different release labels), tests immutable update /
rollback, credentials/recreation, HTTPS rejection and stop/recovery. Only this
unique Compose project is removed. Reports never contain tokens or private paths.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from api_helpers import jpeg, metadata, multipart  # noqa: E402
from sonar_vision_api.dev_tls import create  # noqa: E402
from sonar_vision_api.token_ops import maintain  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args(argv)
    project = 'sonar23-ops-' + uuid4().hex[:12]
    checks = []
    images = []
    completed = False
    WORK = ROOT / '.local'
    WORK.mkdir(exist_ok=True)
    old_umask = os.umask(0o077)
    try:
        with TemporaryDirectory(prefix='issue23-', dir=WORK) as temp:
            private = Path(temp)
            tls = create(private / 'tls')
            models = private / 'models'
            models.mkdir()
            tokens = private / 'tokens'
            original = private / 'original.token'
            maintain(tokens, 'glasses-01', 'provision', original)
            with socket.socket() as available:
                available.bind(('127.0.0.1', 0))
                port = available.getsockname()[1]
            env = {**os.environ, 'SONAR_AWS_BIND_IP': '127.0.0.1',
                   'SONAR_HOST_TLS_DIR': str(private / 'tls'),
                   'SONAR_HOST_TOKENS_FILE': str(tokens),
                   'SONAR_HOST_MODELS_DIR': str(models),
                   'SONAR_API_BACKEND': 'simulated', 'SONAR_API_PORT': str(port),
                   'SONAR_UID': str(os.getuid()), 'SONAR_GID': str(os.getgid())}
            if os.getuid() == 0:
                raise RuntimeError('run operational smoke as a non-root operator')
            command = ['docker', 'compose', '-p', project, '-f', str(ROOT / 'compose.aws.yaml')]

            def compose(*words):
                return subprocess.run(command + list(words), cwd=ROOT, env=env,
                    check=True, capture_output=True, text=True)

            def check(name, condition):
                checks.append({'check': name, 'passed': bool(condition)})
                print(('OK ' if condition else 'FAIL ') + name, flush=True)
                if not condition:
                    raise RuntimeError(name)

            def request(token=None, ca=None):
                import http.client
                connection = http.client.HTTPSConnection('localhost', port,
                    context=ssl.create_default_context(cafile=str(ca or tls['ca'])), timeout=3)
                body, content_type = multipart(metadata(session_id=uuid4().hex), jpeg())
                headers = {'Content-Type': content_type}
                if token is not None:
                    headers['Authorization'] = 'Bearer ' + token
                try:
                    connection.request('POST', '/v1/inference', body, headers)
                    response = connection.getresponse()
                    response.read()
                    return response.status
                finally:
                    connection.close()

            try:
                for release in ('baseline', 'update'):
                    iid = private / (release + '.iid')
                    subprocess.run(['docker', 'build', '--build-arg', 'EXTRAS=api',
                        '--label', 'org.opencontainers.image.revision=uncommitted-issue23-' + release,
                        '--iidfile', str(iid), '-t', project + ':' + release, str(ROOT)],
                        check=True, capture_output=True, text=True)
                    images.append(iid.read_text().strip())
                env['SONAR_AWS_IMAGE_ID'] = images[0]
                platform = json.loads(subprocess.run(['docker', 'image', 'inspect', images[0]],
                    check=True, capture_output=True, text=True).stdout)[0]
                target = platform['Os'] + '/' + platform['Architecture']
                subprocess.run([sys.executable, 'scripts/check_aws_release.py',
                                '--target-platform', target], cwd=ROOT,
                               env=env, check=True, capture_output=True, text=True)
                compose('up', '-d', '--wait', '--wait-timeout', '90')
                old = original.read_text().strip()
                check('authorized HTTPS JPEG receives 200', request(old) == 200)
                check('missing credential receives 401', request() == 401)
                wrong = create(private / 'wrong-ca')
                rejected = False
                try:
                    request(old, wrong['ca'])
                except ssl.SSLCertVerificationError:
                    rejected = True
                check('untrusted CA rejected without TLS bypass', rejected)
                rotated = private / 'rotated.token'
                maintain(tokens, 'glasses-01', 'rotate', rotated)
                new = rotated.read_text().strip()
                compose('up', '-d', '--force-recreate', '--wait', '--wait-timeout', '90')
                check('old credential revoked after recreation', request(old) == 401)
                check('rotated credential receives 200', request(new) == 200)
                env['SONAR_AWS_IMAGE_ID'] = images[1]
                compose('up', '-d', '--wait', '--wait-timeout', '90')
                inspect = json.loads(subprocess.run(['docker', 'inspect', compose('ps', '-q', 'api').stdout.strip()],
                    check=True, capture_output=True, text=True).stdout)[0]
                check('immutable update loads requested image', inspect['Image'] == images[1] and request(new) == 200)
                env['SONAR_AWS_IMAGE_ID'] = images[0]
                compose('up', '-d', '--wait', '--wait-timeout', '90')
                inspect = json.loads(subprocess.run(['docker', 'inspect', compose('ps', '-q', 'api').stdout.strip()],
                    check=True, capture_output=True, text=True).stdout)[0]
                check('rollback loads original immutable image', inspect['Image'] == images[0] and request(new) == 200)
                check('non-root readonly limited service',
                      inspect['Config']['User'].split(':')[0] != '0' and
                      inspect['HostConfig']['ReadonlyRootfs'] and
                      inspect['HostConfig']['Memory'] == 3*1024**3 and
                      inspect['HostConfig']['NanoCpus'] == 4*10**9)
                compose('stop', '-t', '15')
                stopped = json.loads(subprocess.run(['docker', 'inspect', compose('ps', '-a', '-q', 'api').stdout.strip()],
                    check=True, capture_output=True, text=True).stdout)[0]
                check('graceful stop avoids SIGKILL', stopped['State']['ExitCode'] in (0, 143))
                unavailable = False
                try:
                    request(new)
                except OSError:
                    unavailable = True
                check('stopped service unreachable', unavailable)
                compose('up', '-d', '--wait', '--wait-timeout', '90')
                check('service recovers after explicit restart', request(new) == 200)
            finally:
                if env.get('SONAR_AWS_IMAGE_ID'):
                    compose('down', '--remove-orphans')
                left = subprocess.run(['docker', 'ps', '-aq', '--filter',
                    'label=com.docker.compose.project=' + project], check=True, capture_output=True, text=True)
                check('owned containers removed', not left.stdout.strip())
                for release in ('baseline', 'update'):
                    subprocess.run(['docker', 'image', 'rm', project + ':' + release],
                                   capture_output=True, check=False)
            completed = True
    finally:
        os.umask(old_umask)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps({'kind': 'local_docker_operational_smoke_not_aws',
            'backend': 'simulated', 'completed': completed, 'image_ids': images, 'checks': checks,
            'hardware_validated': False, 'cloud_action_taken': False}, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
