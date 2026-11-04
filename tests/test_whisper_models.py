import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from backend_app.modules.idea_radar import media, whisper_models


def snapshot(root, repo='Systran/faster-whisper-base', revision='offline-test'):
    repository = root / ('models--' + repo.replace('/', '--'))
    model = repository / 'snapshots' / revision
    model.mkdir(parents=True)
    for name in (*whisper_models.REQUIRED_MODEL_FILES, 'vocabulary.txt'):
        (model / name).write_text('test model data', encoding='utf-8')
    (repository / 'refs').mkdir()
    (repository / 'refs' / 'main').write_text(revision, encoding='utf-8')
    return model


def test_bundled_model_wins_over_empty_custom_download_cache(tmp_path):
    home = tmp_path / 'resources' / 'huggingface'
    model = snapshot(home / 'hub')
    source, offline = whisper_models.resolve_whisper_model('base', tmp_path / 'user-downloads' / '.sau-cache', {
        'SAU_PACKAGED': '1', 'SAU_BUNDLED_HUGGINGFACE_HOME': str(home),
    })
    assert Path(source) == model.resolve()
    assert offline is True


def test_existing_huggingface_environment_still_finds_packaged_model(tmp_path):
    home = tmp_path / 'huggingface'
    model = snapshot(home / 'hub')
    source, offline = whisper_models.resolve_whisper_model('base', tmp_path / 'empty', {
        'SAU_PACKAGED': '1', 'HF_HOME': str(home),
    })
    assert Path(source) == model and offline


def test_explicit_local_model_uses_offline_loading(tmp_path):
    model = snapshot(tmp_path)
    assert whisper_models.resolve_whisper_model(str(model), environ={'SAU_PACKAGED': '1'}) == (str(model), True)


@pytest.mark.parametrize('filename', ['model.bin', 'config.json', 'tokenizer.json', 'vocabulary.txt'])
def test_incomplete_bundled_models_fail_without_online_fallback(tmp_path, filename):
    home = tmp_path / 'huggingface'
    model = snapshot(home / 'hub')
    (model / filename).unlink()
    with pytest.raises(RuntimeError, match='完整安装包'):
        whisper_models.resolve_whisper_model('base', environ={
            'SAU_PACKAGED': '1', 'SAU_BUNDLED_HUGGINGFACE_HOME': str(home),
        })


def test_empty_model_file_is_incomplete(tmp_path):
    model = snapshot(tmp_path)
    (model / 'model.bin').write_bytes(b'')
    assert whisper_models.complete_model(model) is False


def test_corrupt_reference_cannot_escape_snapshot_directory(tmp_path):
    snapshot(tmp_path)
    (tmp_path / 'models--Systran--faster-whisper-base' / 'refs' / 'main').write_text('../../outside')
    assert whisper_models.cached_snapshot(tmp_path, 'Systran/faster-whisper-base') is None


def test_transcription_passes_local_snapshot_instead_of_model_alias(tmp_path, monkeypatch):
    home = tmp_path / 'huggingface'
    model = snapshot(home / 'hub')
    monkeypatch.setenv('SAU_PACKAGED', '1')
    monkeypatch.setenv('SAU_BUNDLED_HUGGINGFACE_HOME', str(home))
    monkeypatch.setenv('IDEA_RADAR_WHISPER_MODEL', 'base')
    whisper = Mock()
    whisper.transcribe.return_value = (iter([]), SimpleNamespace(duration=1, language='zh'))
    factory = Mock(return_value=whisper)
    monkeypatch.setitem(sys.modules, 'faster_whisper', SimpleNamespace(WhisperModel=factory))
    audio = tmp_path / 'input.wav'
    audio.write_bytes(b'audio')
    result, name = media.transcribe_media(audio, download_root=tmp_path / 'empty-cache')
    assert factory.call_args.args == (str(model),)
    assert factory.call_args.kwargs['local_files_only'] is True
    assert result['engine'] == 'faster-whisper' and name == 'base'


def test_unbundled_custom_model_has_clear_offline_error(tmp_path):
    with pytest.raises(RuntimeError, match='默认模型为 base'):
        whisper_models.resolve_whisper_model('unbundled-model', tmp_path, {'SAU_PACKAGED': '1'})
