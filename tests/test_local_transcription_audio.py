"""Exercise the decoder used by transcription without downloading a model."""
import io
import wave

from faster_whisper.audio import decode_audio


def test_faster_whisper_decodes_wav_with_installed_pyav():
    audio = io.BytesIO()
    with wave.open(audio, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x00\x00" * 1600)
    audio.seek(0)
    decoded = decode_audio(audio, sampling_rate=16000)
    assert len(decoded) == 1600
    assert decoded.dtype.name == "float32"
