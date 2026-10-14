"""Process already sampled RGB frames; this module never opens video files."""
import numpy as np


class ProcessorRoute:
    def __init__(self, processor, route):
        if route not in ('images', 'video'):
            raise ValueError('Unknown processor route')
        self.processor, self.route = processor, route

    def __getattr__(self, name):
        return getattr(self.processor, name)

    def __call__(self, *, images, **kwargs):
        if self.route == 'images':
            return self.processor(images=images, **kwargs)
        return self.processor(videos=[np.stack([np.asarray(im) for im in images])], **kwargs)
