"""Count saved text with named reference encodings; not a provider-usage reconstruction."""
import hashlib
import importlib.metadata
import json
from pathlib import Path

import tiktoken

ROOT = Path(__file__).resolve().parent
PROBE = ROOT.parent / '2026-10-23-two-case-probe'
encodings = {name: tiktoken.get_encoding(name) for name in ['o200k_base', 'cl100k_base']}
result = {
    'tiktoken_version': importlib.metadata.version('tiktoken'),
    'scope': 'Exact saved-text counts under named reference encodings. The actual agent model tokenizer, total input, tool overhead, reasoning and output usage were not captured. These are not provider billing counts.',
    'common_prompt': {}, 'cases': {}}


def measure(path):
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    return {'utf8_bytes': len(raw), 'characters': len(text), 'whitespace_words': len(text.split()),
            'sha256': hashlib.sha256(raw).hexdigest(),
            'reference_tokens': {name: len(encoding.encode(text, disallowed_special=()))
                                 for name, encoding in encodings.items()}}


result['common_prompt'] = measure(PROBE / 'common_prompt.md')
for name in ['case-c193', 'case-7b4e']:
    packet = json.loads((PROBE / 'inputs' / f'{name}.json').read_text())
    result['cases'][name] = {'transactions': len(packet['transactions']),
                           'accounts': len(packet['accounts']),
                           'markdown_packet': measure(PROBE / 'inputs' / f'{name}.md'),
                           'json_packet': measure(PROBE / 'inputs' / f'{name}.json'),
                           'submitted_request_text': measure(PROBE / 'inputs' / f'{name}.request.md'),
                           'saved_response_json': measure(PROBE / 'assessments' / f'{name}.json')}
(ROOT / 'context-measurements.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
