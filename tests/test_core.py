import numpy as np
import noisereducecustom as nrc


def _make_tone_plus_noise(sr=16000, duration=1.0, seed=0):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    signal = 0.5 * np.sin(2 * np.pi * 440 * t)
    rng = np.random.default_rng(seed)
    noise = 0.05 * rng.standard_normal(len(t))
    return (signal + noise).astype(np.float32)


def test_stationary_mono():
    sr = 16000
    audio = _make_tone_plus_noise(sr)
    reduced = nrc.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=0.95)
    assert reduced.shape == audio.shape
    assert reduced.dtype == np.float32
    assert np.isfinite(reduced).all()


def test_nonstationary_mono():
    sr = 16000
    audio = _make_tone_plus_noise(sr, seed=1)
    reduced = nrc.reduce_noise(y=audio, sr=sr, stationary=False, prop_decrease=0.8)
    assert reduced.shape == audio.shape
    assert np.isfinite(reduced).all()


def test_stationary_with_separate_noise_clip():
    sr = 16000
    audio = _make_tone_plus_noise(sr, seed=2)
    noise_only = 0.05 * np.random.default_rng(3).standard_normal(sr)
    reduced = nrc.reduce_noise(y=audio, sr=sr, y_noise=noise_only, stationary=True)
    assert reduced.shape == audio.shape


def test_multichannel_stereo():
    sr = 8000
    left = _make_tone_plus_noise(sr, seed=4)
    right = _make_tone_plus_noise(sr, seed=5)
    stereo = np.stack([left, right], axis=1)  # shape (n_frames, 2)
    reduced = nrc.reduce_noise(y=stereo, sr=sr, stationary=True)
    assert reduced.shape == stereo.shape


def test_chunked_processing_matches_shape():
    sr = 8000
    audio = _make_tone_plus_noise(sr, duration=2.0, seed=6)
    reduced = nrc.reduce_noise(y=audio, sr=sr, stationary=True, chunk_size=4000, padding=1000)
    assert reduced.shape == audio.shape


def test_band_limited_noise_generator():
    noise = nrc.band_limited_noise(min_freq=1000, max_freq=2000, samples=4096, samplerate=16000)
    assert noise.shape == (4096,)
    assert np.max(np.abs(noise)) <= 1.0 + 1e-6


def test_prop_decrease_zero_is_near_identity():
    sr = 16000
    audio = _make_tone_plus_noise(sr, seed=7)
    reduced = nrc.reduce_noise(y=audio, sr=sr, stationary=True, prop_decrease=0.0)
    # with prop_decrease=0 the mask should barely touch the signal
    assert np.corrcoef(audio, reduced[: len(audio)])[0, 1] > 0.9


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("All tests passed.")
