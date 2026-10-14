"""Sequential video decoder; never passes a full video to the model."""
from .stream import nonnegative


def video_frames(path, max_media_ms=None):
    if max_media_ms is not None:
        nonnegative(max_media_ms, 'max_media_ms')
    import av
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        origin = None
        for frame in container.decode(stream):
            if frame.pts is None:
                raise ValueError('Missing source PTS; cannot establish causal timing')
            pts_ms = float(frame.pts * stream.time_base) * 1000
            if origin is None:
                origin = pts_ms
            if max_media_ms is not None and pts_ms - origin > max_media_ms:
                break
            yield frame.to_ndarray(format='rgb24'), pts_ms - origin
