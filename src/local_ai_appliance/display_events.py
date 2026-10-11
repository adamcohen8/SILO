"""Data-only live output with independent byte/event limits; no host actions."""
from .contracts import Progress
from .folders import AccessDenied


class DisplayEvents:
    MAX_EVENTS = 128
    MAX_TEXT = 64 * 1024

    def __init__(self, progress, text):
        self.progress, self.text = progress, text
        self.events = self.bytes = 0

    def handle(self, value):
        self.events += 1
        if self.events > self.MAX_EVENTS or not isinstance(value, dict):
            raise AccessDenied('Invalid live display event')
        kind = value.get('type')
        if kind == 'reset' and set(value) == {'type'}:
            self.text(None)
        elif kind == 'text' and set(value) == {'type', 'text'}:
            text = value['text']
            if not isinstance(text, str) or not text or len(text.encode('utf-8')) > 1024:
                raise AccessDenied('Invalid live display text')
            self.bytes += len(text.encode('utf-8'))
            if self.bytes > self.MAX_TEXT:
                raise AccessDenied('Live display text exceeds the request limit')
            self.text(text)
        elif kind == 'progress' and set(value) == {'type', 'stage', 'model_calls', 'tool_calls'}:
            try:
                event = Progress(value['stage'], value['model_calls'], value['tool_calls'])
            except ValueError as error:
                raise AccessDenied('Invalid live progress') from error
            if event.stage not in {'model', 'tools'} or event.model_calls > 16 or event.tool_calls > 48:
                raise AccessDenied('Invalid live progress bounds')
            self.progress(event)
        else:
            raise AccessDenied('Unregistered live display event')
