"""Small generated interface sounds; no external assets are required."""
from array import array
import math

from .preferences import get_preferences


_sounds = {}


def play_sound(pygame, kind):
    if not get_preferences()['sound']:
        return
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2)
        if kind not in _sounds:
            frequency, duration = ((740, .07) if kind == 'trade' else
                                   (440, .22))
            sample_rate, _format, channels = pygame.mixer.get_init()
            samples = array('h')
            for index in range(round(sample_rate * duration)):
                fade = 1 - index / (sample_rate * duration)
                value = round(5000 * fade * math.sin(
                    2 * math.pi * frequency * index / sample_rate))
                samples.extend([value] * channels)
            _sounds[kind] = pygame.mixer.Sound(buffer=samples)
        _sounds[kind].play()
    except pygame.error:
        pass
