"""Cliente Gemini único para todo o projeto."""
from functools import lru_cache

from google import genai
from google.genai import types

import config

# Erros temporários do lado do Google: vale tentar de novo.
CODIGOS_TRANSITORIOS = [429, 500, 502, 503, 504]


@lru_cache(maxsize=1)
def cliente() -> genai.Client:
    # Por padrão o SDK NÃO repete chamadas que falham. Aqui ele tenta até 4 vezes,
    # esperando ~2s, 4s, 8s... (com variação aleatória) entre as tentativas.
    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=4,
                initial_delay=2.0,
                max_delay=20.0,
                http_status_codes=CODIGOS_TRANSITORIOS,
            )
        ),
    )


def carregar_prompt(nome: str) -> str:
    return (config.PROMPTS / nome).read_text(encoding="utf-8")
