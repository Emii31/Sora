"""Conservative sentence boundaries for incremental local voice output."""
import re


class SentenceBuffer:
    # Ambiguous abbreviations wait for a later boundary or validated completion.
    abbreviations = {'mr', 'mrs', 'ms', 'dr', 'prof', 'st', 'jr', 'sr', 'vs', 'etc', 'e.g', 'i.e'}
    boundary = re.compile(r'[.!?。！？]+[\"\'”’)]*(?:\s+|(?=[^\x00-\x7f]))')

    def __init__(self):
        self.pending = ''

    def feed(self, text):
        self.pending += text
        ready = []
        offset = 0
        for match in self.boundary.finditer(self.pending):
            if match.group().startswith('...'):
                continue
            if match.group()[0] == '.':
                prefix = self.pending[:match.start()]
                word = re.search(r'([\w.]+)$', prefix)
                word = word.group(1) if word else ''
                if (word.lower() in self.abbreviations or len(word) == 1
                        or word.isdigit() or '.' in word):
                    continue
            ready.append(self.pending[offset:match.end()])
            offset = match.end()
        self.pending = self.pending[offset:]
        return ready

    def finish(self):
        remaining, self.pending = self.pending, ''
        return [remaining] if remaining.strip() else []
