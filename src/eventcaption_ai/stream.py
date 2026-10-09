"""Causal, immutable snapshots and bounded prefix buffer."""
from collections import deque
from dataclasses import dataclass
import math

import numpy as np


def nonnegative(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'{name} must be finite and nonnegative')


@dataclass(frozen=True)
class Frame:
    index: int
    media_ms: float
    arrival_ms: float
    shape: tuple
    pixels: bytes

    def __post_init__(self):
        nonnegative(self.media_ms, 'media_ms')
        nonnegative(self.arrival_ms, 'arrival_ms')
        if type(self.index) is not int or self.index < 0 or not isinstance(self.pixels, bytes):
            raise ValueError('Invalid immutable frame')
        if not isinstance(self.shape, tuple) or len(self.shape) != 3 or self.shape[2] != 3 or any(type(n) is not int or n <= 0 for n in self.shape):
            raise ValueError('Invalid RGB shape')
        if len(self.pixels) != math.prod(self.shape):
            raise ValueError('RGB bytes do not match shape')

    @property
    def evidence_id(self):
        return f'frame:{self.index}'

    def rgb(self):
        return np.frombuffer(self.pixels, dtype=np.uint8).reshape(self.shape)


@dataclass(frozen=True)
class Snapshot:
    frames: tuple[Frame, ...]
    cutoff_ms: float

    def __post_init__(self):
        nonnegative(self.cutoff_ms, 'cutoff')
        if not isinstance(self.frames, tuple) or not self.frames:
            raise ValueError('Snapshot requires immutable nonempty frames')
        if any(not isinstance(f, Frame) or f.media_ms > self.cutoff_ms for f in self.frames):
            raise ValueError('Invalid/future frame in snapshot')
        if any(a.index >= b.index or a.media_ms >= b.media_ms for a, b in zip(self.frames, self.frames[1:])):
            raise ValueError('Snapshot frames must be strictly ordered')

    def evidence(self):
        return {f.evidence_id: f.media_ms for f in self.frames}


class PrefixBuffer:
    def __init__(self, max_frames=4, sample_fps=2, max_frame_bytes=1920 * 1080 * 3):
        if type(max_frames) is not int or max_frames < 1:
            raise ValueError('max_frames must be positive integer')
        nonnegative(sample_fps, 'sample_fps')
        if sample_fps == 0 or type(max_frame_bytes) is not int or max_frame_bytes < 1:
            raise ValueError('Invalid buffer limits')
        self.frames = deque(maxlen=max_frames)
        self.period = 1000 / sample_fps
        self.max_frame_bytes = max_frame_bytes
        self.last_index = self.last_media = self.last_arrival = -1
        self.next_sample = 0
        self.gaps = 0

    def push(self, rgb, index, media_ms, arrival_ms):
        nonnegative(media_ms, 'media_ms')
        nonnegative(arrival_ms, 'arrival_ms')
        if type(index) is not int or index <= self.last_index or media_ms <= self.last_media or arrival_ms < self.last_arrival:
            raise ValueError('Nonmonotonic frame index or timestamp')
        if not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.size:
            raise ValueError('Expected nonempty HxWx3 uint8 RGB')
        if rgb.nbytes > self.max_frame_bytes:
            raise ValueError('Frame exceeds configured byte limit')
        if self.last_media >= 0 and media_ms - self.last_media > 2 * self.period:
            self.gaps += 1
        self.last_index, self.last_media, self.last_arrival = index, media_ms, arrival_ms
        if media_ms < self.next_sample:
            return False
        self.frames.append(Frame(index, media_ms, arrival_ms, rgb.shape, rgb.tobytes()))
        self.next_sample = (math.floor(media_ms / self.period) + 1) * self.period
        return True

    def snapshot(self):
        if not self.frames:
            raise ValueError('No sampled frames')
        return Snapshot(tuple(self.frames), self.frames[-1].media_ms)
