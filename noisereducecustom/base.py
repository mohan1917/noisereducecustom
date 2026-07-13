"""
base.py
-------
Shared plumbing for both spectral-gating strategies (stationary and
non-stationary). Subclasses only need to implement `_process_channel`,
which takes one channel of raw float audio and returns the denoised
version of that same channel.

Two things are handled here so subclasses don't have to:

1. Multi-channel audio: audio is normalized to (n_channels, n_frames)
   and each channel is denoised independently, then re-stacked, then
   restored to whatever layout the input originally had.

2. Chunked processing: very long recordings are processed in
   overlapping chunks (with `padding` extra samples on each side, which
   get trimmed off after filtering) so memory usage stays bounded and
   the noise/mask statistics stay locally relevant instead of being
   averaged over an entire multi-hour file.
"""

import numpy as np


class SpectralGateBase:
    def __init__(self, y, sr, n_fft=1024, win_length=None, hop_length=None,
                 chunk_size=None, padding=30000):
        y2d, layout = self._reshape(y)
        self.y = y2d
        self.layout = layout
        self.dtype = np.asarray(y).dtype
        self.n_channels, self.n_frames = self.y.shape

        self.sr = sr
        self.n_fft = n_fft
        self.win_length = win_length if win_length is not None else n_fft
        self.hop_length = hop_length if hop_length is not None else self.win_length // 4
        self.chunk_size = chunk_size
        self.padding = padding

    @staticmethod
    def _reshape(y):
        from .utils import ensure_channel_first
        return ensure_channel_first(y)

    def _process_channel(self, channel):
        """Subclasses implement the actual gating algorithm here."""
        raise NotImplementedError

    def _filter_span(self, channel, start, end):
        """
        Filter one span [start, end) of a channel, padding on both
        sides by `self.padding` samples for context, then trimming the
        padding back off after filtering.
        """
        i1 = start - self.padding
        i2 = end + self.padding

        pad_left = max(0, -i1)
        pad_right = max(0, i2 - len(channel))
        i1c = max(0, i1)
        i2c = min(len(channel), i2)

        segment = channel[i1c:i2c]
        if pad_left or pad_right:
            segment = np.pad(segment, (pad_left, pad_right))

        filtered = self._process_channel(segment)

        trim_start = self.padding
        trim_end = trim_start + (end - start)
        return filtered[trim_start:trim_end]

    def _filter_channel(self, channel):
        """Filter a full channel, chunked if chunk_size is set."""
        n = len(channel)
        if not self.chunk_size or n <= self.chunk_size:
            return self._filter_span(channel, 0, n)

        out = np.zeros(n, dtype=np.float32)
        for start in range(0, n, self.chunk_size):
            end = min(start + self.chunk_size, n)
            out[start:end] = self._filter_span(channel, start, end)
        return out

    def get_traces(self):
        """Run the gate over every channel and return the denoised audio,
        re-shaped back to whatever layout the input originally had."""
        out = np.zeros_like(self.y, dtype=np.float32)
        for ch in range(self.n_channels):
            out[ch] = self._filter_channel(self.y[ch])

        out = out.astype(np.float32)
        if self.layout == "flat":
            return out[0]
        elif self.layout == "channels_last":
            return out.T  # back to (n_frames, n_channels)
        return out  # "channels_first" stays (n_channels, n_frames)
