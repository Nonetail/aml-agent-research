"""Count the pinned NVIDIA tokenizer/template locally; never performs inference.

Counts are exact for the public checkpoint's template, not a guarantee that the
hosted service uses identical framing. Calibrate against returned prompt_tokens.
"""
from pathlib import Path
from transformers import AutoTokenizer

TOKENIZER_DIR = Path(__file__).resolve().parent / 'tokenizer'
TOKENIZER_REPOSITORY = 'nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4'
TOKENIZER_REVISION = 'bee7596271d1495f6992ae224aefde4410e816b8'


def provider_schema(value):
    if isinstance(value, dict):
        return {k: provider_schema(v) for k, v in value.items() if k != 'uniqueItems'}
    if isinstance(value, list):
        return [provider_schema(v) for v in value]
    return value


class ContextTokens:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(TOKENIZER_DIR, local_files_only=True)

    def text(self, value):
        return len(self.tokenizer.backend_tokenizer.encode(value, add_special_tokens=False).ids)

    def render(self, request):
        return self.tokenizer.apply_chat_template(
            request['messages'], tools=provider_schema(request.get('tools', [])),
            tokenize=False, add_generation_prompt=True, enable_thinking=False)

    def count_request(self, request):
        return self.text(self.render(request))

    def admission(self, request, context_cap=200000, safety_tokens=4096):
        prompt_tokens = self.count_request(request)
        output_tokens = request.get('max_tokens')
        if not isinstance(output_tokens, int) or output_tokens < 1:
            raise ValueError('An explicit positive output reserve is required')
        total = prompt_tokens + output_tokens + safety_tokens
        return {'local_prompt_tokens': prompt_tokens, 'output_reserve': output_tokens,
                'safety_tokens': safety_tokens, 'reserved_total': total,
                'context_cap': context_cap, 'admitted': total <= context_cap,
                'accounting': 'pinned_public_tokenizer_and_chat_template'}
