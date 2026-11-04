"""Locate complete Whisper snapshots without contacting Hugging Face."""
import os
from pathlib import Path


REQUIRED_MODEL_FILES = ('config.json', 'model.bin', 'tokenizer.json')


def complete_model(directory):
    directory = Path(directory)
    try:
        required = [directory / name for name in REQUIRED_MODEL_FILES]
        vocabulary = [directory / name for name in ('vocabulary.txt', 'vocabulary.json')]
        return all(path.is_file() and path.stat().st_size > 0 for path in required) and any(
            path.is_file() and path.stat().st_size > 0 for path in vocabulary
        )
    except OSError:
        return False


def cached_snapshot(cache_root, repo_id):
    repository = Path(cache_root) / ('models--' + repo_id.replace('/', '--'))
    reference = repository / 'refs' / 'main'
    try:
        revision = reference.read_text(encoding='utf-8').strip()
        if not revision or revision in ('.', '..') or '/' in revision or '\\' in revision:
            return None
        snapshots = (repository / 'snapshots').resolve()
        snapshot = (snapshots / revision).resolve()
        snapshot.relative_to(snapshots)
        return snapshot if complete_model(snapshot) else None
    except (OSError, ValueError):
        return None


def resolve_whisper_model(model, download_root=None, environ=None):
    env = os.environ if environ is None else environ
    value = str(model)
    explicit = Path(value).expanduser()
    if explicit.is_dir():
        if not complete_model(explicit):
            raise RuntimeError('本地 Whisper 模型文件不完整，需要 config.json、model.bin、tokenizer.json 和 vocabulary 文件')
        return str(explicit.resolve()), True

    repo_id = value if '/' in value else f'Systran/faster-whisper-{value}'
    cache_roots = []
    bundled = env.get('SAU_BUNDLED_HUGGINGFACE_HOME')
    if bundled:
        cache_roots.append(Path(bundled) / 'hub')
    if env.get('HUGGINGFACE_HUB_CACHE'):
        cache_roots.append(Path(env['HUGGINGFACE_HUB_CACHE']))
    if env.get('HF_HOME'):
        cache_roots.append(Path(env['HF_HOME']) / 'hub')
    if download_root:
        cache_roots.append(Path(download_root))
    packaged = env.get('SAU_PACKAGED') == '1'
    if not packaged:
        cache_roots.append(Path(__file__).resolve().parents[3] / 'build-resources' / 'huggingface' / 'hub')
    for cache_root in cache_roots:
        snapshot = cached_snapshot(cache_root, repo_id)
        if snapshot:
            return str(snapshot), True
    if packaged:
        raise RuntimeError(f'未找到完整的内置 Whisper {value} 模型，请重新安装包含语音模型的完整安装包；默认模型为 base')
    return value, False
