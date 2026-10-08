"""Read-only #23 preflight. Creates no AWS resources and prints no private paths.

Requires Compose inputs documented in docs/aws-operation.md. Validates immutable
image identity, bind inputs, model hashes, credential snapshot and TLS key pair.
This checks local operator inputs; it does not prove IAM, SG or cloud readiness.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import stat
import subprocess

from sonar_vision_api.auth import TokenStore

ROOT = Path(__file__).resolve().parents[1]


def required(env, key):
    value = env.get(key)
    if not value:
        raise ValueError(f"{key} required")
    return value


def private_file(path):
    path = Path(path)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or (os.name != 'nt' and mode & 0o077):
        raise ValueError('credentials and TLS keys must be regular private files (0600)')
    return path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inspect_inputs(env, *, parallel=False, audio=False):
    image = required(env, 'SONAR_AWS_IMAGE_ID')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', image):
        raise ValueError('SONAR_AWS_IMAGE_ID must be a complete local immutable image ID')
    tls = Path(required(env, 'SONAR_HOST_TLS_DIR'))
    tokens = private_file(required(env, 'SONAR_HOST_TOKENS_FILE'))
    TokenStore.from_file(tokens)
    key = private_file(tls / 'server-key.pem')
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(tls / 'server.pem', key)
    ssl.create_default_context(cafile=str(tls / 'ca.pem'))
    models = Path(required(env, 'SONAR_HOST_MODELS_DIR'))
    if not models.is_dir():
        raise ValueError('model directory missing')
    backend = env.get('SONAR_API_BACKEND', 'simulated')
    if backend not in ('simulated', 'ultralytics'):
        raise ValueError('unsupported backend')
    hashes = {}
    if backend == 'ultralytics':
        for path_key, sha_key in [
            ('SONAR_API_WEIGHTS_IN_CONTAINER', 'SONAR_API_WEIGHTS_SHA256'),
            ('SONAR_API_STAIR_WEIGHTS_IN_CONTAINER', 'SONAR_API_STAIR_WEIGHTS_SHA256'),
        ]:
            name = env.get(path_key)
            if path_key.startswith('SONAR_API_STAIR') and not name and not parallel:
                continue
            name = required(env, path_key)
            relative = Path(name)
            if relative.parent != Path('/models'):
                raise ValueError('weights must be immediate /models children')
            expected = required(env, sha_key)
            actual = digest(models / relative.name)
            if not re.fullmatch(r'[0-9a-f]{64}', expected) or actual != expected:
                raise ValueError(f'{sha_key} mismatch')
            hashes[sha_key] = actual
    if parallel:
        if backend != 'ultralytics':
            raise ValueError('experimental parallel runner requires general and stair weights')
        runner = Path(required(env, 'SONAR_HOST_PARALLEL_RUNNER'))
        expected = required(env, 'SONAR_PARALLEL_RUNNER_SHA256')
        actual = digest(runner)
        if not re.fullmatch(r'[0-9a-f]{64}', expected) or actual != expected:
            raise ValueError('experimental runner hash mismatch')
        hashes['experimental_runner_sha256'] = actual
    if audio:
        from sonar_vision_api.runtime_options import load_audio_config
        policy = Path(required(env, 'SONAR_HOST_AUDIO_CONFIG'))
        expected = required(env, 'SONAR_AUDIO_CONFIG_SHA256')
        actual = digest(policy)
        if not re.fullmatch(r'[0-9a-f]{64}', expected) or actual != expected:
            raise ValueError('reviewed audio configuration hash mismatch')
        load_audio_config(policy)
        hashes['audio_config_sha256'] = actual
    bind = env.get('SONAR_AWS_BIND_IP', '127.0.0.1')
    if bind not in ('127.0.0.1', '0.0.0.0'):
        raise ValueError('unsupported bind address')
    return {'image_id': image, 'backend': backend, 'experimental_parallel': parallel,
            'public_bind_requires_owned_security_group': bind == '0.0.0.0',
            'model_hashes': hashes, 'credentials_validated': True,
            'tls_key_pair_loadable': True, 'endpoint_tls_verified': False,
            'cloud_action_taken': False}


def validate_image(info, expected_id, target_platform):
    if info['Id'] != expected_id:
        raise ValueError('image identity mismatch')
    platform = info['Os'] + '/' + info['Architecture']
    if platform != target_platform:
        raise ValueError('image platform mismatch')
    return platform


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parallel', action='store_true')
    parser.add_argument('--target-platform', choices=('linux/amd64', 'linux/arm64'),
                        default='linux/amd64', help='ARM is only for explicit local smoke')
    parser.add_argument('--audio', action='store_true', help='validate optional reviewed audio policy')
    args = parser.parse_args(argv)
    try:
        result = inspect_inputs(os.environ, parallel=args.parallel, audio=args.audio)
        image = subprocess.run(['docker', 'image', 'inspect', result['image_id']],
                               check=True, capture_output=True, text=True)
        info = json.loads(image.stdout)[0]
        result['platform'] = validate_image(info, result['image_id'], args.target_platform)
        result['source_commit_label'] = (info.get('Config', {}).get('Labels') or {}).get(
            'org.opencontainers.image.revision')
        command = ['docker', 'compose', '-f', 'compose.aws.yaml']
        if args.parallel:
            command += ['-f', 'compose.aws.parallel.yaml']
        if args.audio:
            command += ['-f', 'compose.aws.audio.yaml']
        config = subprocess.run(command + ['config', '--format', 'json'], cwd=ROOT,
                                check=True, capture_output=True, text=True)
        user = json.loads(config.stdout)['services']['api']['user'].split(':')[0]
        if user in ('0', 'root'):
            raise ValueError('operator deployment must not run as root')
    except (OSError, ValueError, subprocess.CalledProcessError):
        parser.exit(2, 'preflight failed: inspect private inputs, hashes and local Docker; no cloud action taken\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
