import numpy as np
import pytest

from eventcaption_ai.stream import Frame, Snapshot, PrefixBuffer
from eventcaption_ai.processing import ProcessorRoute
from eventcaption_ai.video import video_frames


def test_bounded_prefix_sampling_and_immutable_pixels():
    buffer = PrefixBuffer(max_frames=2, sample_fps=2)
    rgb = np.zeros((2, 2, 3), dtype=np.uint8)
    assert buffer.push(rgb, 0, 0, 0)
    snap = buffer.snapshot()
    rgb[:] = 255
    assert not snap.frames[0].rgb().any()
    assert not buffer.push(rgb, 1, 100, 100)
    assert buffer.push(rgb, 2, 500, 500)
    assert buffer.push(rgb, 3, 2000, 2000)
    assert len(buffer.snapshot().frames) == 2
    assert buffer.gaps == 1
    assert snap.evidence() == {'frame:0': 0}
    with pytest.raises(ValueError): buffer.push(rgb, 3, 2500, 2500)
    with pytest.raises(ValueError): buffer.push(rgb.astype(float), 4, 2500, 2500)
    with pytest.raises(ValueError): PrefixBuffer(max_frame_bytes=1).push(rgb, 0, 0, 0)
    with pytest.raises(ValueError): PrefixBuffer().snapshot()


@pytest.mark.parametrize('kwargs', [{'max_frames':0}, {'sample_fps':0}, {'sample_fps':float('nan')}, {'max_frame_bytes':0}])
def test_invalid_buffer_limits(kwargs):
    with pytest.raises(ValueError): PrefixBuffer(**kwargs)


def test_invalid_frames_and_snapshots():
    frame = Frame(0, 100, 100, (1, 1, 3), bytes(3))
    for frames, cutoff in [((), 100), ((frame,), 99), ((frame,frame), 100)]:
        with pytest.raises(ValueError): Snapshot(frames, cutoff)
    for args in [(-1,0,0,(1,1,3),bytes(3)), (0,0,0,(1,1,4),bytes(4)), (0,0,0,(1,1,3),bytes(2))]:
        with pytest.raises(ValueError): Frame(*args)


def test_processor_routes_only_given_images():
    class Processor:
        tokenizer = 'tokenizer'
        def __call__(self, **kwargs): return kwargs
    images = [np.zeros((2,2,3), dtype=np.uint8)]
    route = ProcessorRoute(Processor(), 'video')
    assert route.tokenizer == 'tokenizer'
    assert route(images=images)['videos'][0].shape == (1,2,2,3)
    assert ProcessorRoute(Processor(), 'images')(images=images)['images'] is images
    with pytest.raises(ValueError): ProcessorRoute(Processor(), 'invalid')


def test_decoder_respects_prefix_and_missing_pts(monkeypatch):
    from types import SimpleNamespace
    import av
    class Container:
        streams = SimpleNamespace(video=[SimpleNamespace(time_base=.001)])
        frames = [SimpleNamespace(pts=t, to_ndarray=lambda **kw: np.zeros((1,1,3),dtype=np.uint8)) for t in (100,1100,2100)]
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def decode(self, stream): return iter(self.frames)
    container = Container()
    monkeypatch.setattr(av,'open',lambda path: container)
    assert [t for _,t in video_frames('mock',1000)] == [0,1000]
    container.frames = [SimpleNamespace(pts=None)]
    with pytest.raises(ValueError): list(video_frames('mock'))
    with pytest.raises(ValueError): list(video_frames('mock',-1))
