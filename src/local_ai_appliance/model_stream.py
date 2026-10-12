"""Bounded SSE assembly. Deltas are display-only; tools require a full reply."""
from .model import AgentError, json_bytes, strict_json


class ChatStream:
    def __init__(self, on_text, *, limit):
        self.on_text, self.limit = on_text, limit
        self.pending = bytearray()
        self.content, self.reasoning, self.calls = '', '', {}
        self.finish = None
        self.done = False
        self.size = 0

    def feed(self, block):
        self.pending.extend(block)
        while b'\n' in self.pending:
            line, _, tail = self.pending.partition(b'\n')
            self.pending = bytearray(tail)
            self._line(bytes(line).rstrip(b'\r'))
        if len(self.pending) > self.limit:
            raise AgentError('Model stream line exceeds the limit')

    def _add(self, value):
        if not isinstance(value, str):
            raise ValueError()
        self.size += len(value.encode('utf-8'))
        if self.size > self.limit:
            raise ValueError()
        return value

    def _line(self, line):
        if not line or line.startswith(b':'):
            return
        try:
            if self.done or not line.startswith(b'data:'):
                raise ValueError()
            data = line[5:].strip()
            if data == b'[DONE]':
                if self.finish is None:
                    raise ValueError()
                self.done = True
                return
            value = strict_json(data)
            choices = value['choices']
            if choices == [] and isinstance(value.get('usage'), dict):
                return
            if not isinstance(choices, list) or len(choices) != 1 or self.finish is not None:
                raise ValueError()
            choice = choices[0]
            if type(choice.get('index')) is not int or choice['index'] != 0:
                raise ValueError()
            delta = choice['delta']
            if (not isinstance(delta, dict) or set(delta) - {'role', 'content', 'reasoning_content', 'tool_calls'}
                    or delta.get('role', 'assistant') != 'assistant'):
                raise ValueError()
            text = self._add('' if delta.get('content') is None else delta['content'])
            self.content += text
            self.reasoning += self._add('' if delta.get('reasoning_content') is None else delta['reasoning_content'])
            if len(self.reasoning.encode('utf-8')) > 64 * 1024:
                raise ValueError()
            tools = delta.get('tool_calls', [])
            if not isinstance(tools, list) or len(tools) > 4:
                raise ValueError()
            for fragment in tools:
                index = fragment['index']
                if type(index) is not int or not 0 <= index < 4 or set(fragment) - {'index', 'id', 'type', 'function'}:
                    raise ValueError()
                call = self.calls.setdefault(index, {'id': '', 'type': 'function', 'function': {'name': '', 'arguments': ''}})
                if fragment.get('type', 'function') != 'function':
                    raise ValueError()
                function = fragment.get('function', {})
                if not isinstance(function, dict) or set(function) - {'name', 'arguments'}:
                    raise ValueError()
                call['id'] += self._add(fragment.get('id', ''))
                for key in ('name', 'arguments'):
                    call['function'][key] += self._add(function.get(key, ''))
            finish = choice.get('finish_reason')
            if finish is not None:
                if finish not in {'stop', 'tool_calls', 'length'}:
                    raise ValueError()
                self.finish = finish
            if text:
                self.on_text(text)  # No reasoning or tool arguments leave this parser.
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
            raise AgentError('Local model returned malformed or incomplete streaming data') from error

    def result(self):
        if self.pending.strip() or not self.done or self.finish is None:
            raise AgentError('Local model stream ended before its complete result')
        if sorted(self.calls) != list(range(len(self.calls))):
            raise AgentError('Local model stream omitted a tool fragment')
        message = {'role': 'assistant', 'content': self.content, 'reasoning_content': self.reasoning,
                   'tool_calls': [self.calls[i] for i in sorted(self.calls)]}
        result = json_bytes({'choices': [{'message': message, 'finish_reason': self.finish}]})
        if len(result) > self.limit:
            raise AgentError('Assembled model stream exceeds the response limit')
        return result
