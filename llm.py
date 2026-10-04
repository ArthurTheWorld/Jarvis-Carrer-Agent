"""Cliente Gemini único para todo o projeto."""
from functools import lru_cache

import httpx
from google import genai
from google.genai import errors, types

import config

# Erros temporários do lado do Google: vale tentar de novo.
CODIGOS_TRANSITORIOS = [429, 500, 502, 503, 504]
TIMEOUT_MS = 30_000  # 30 segundos por tentativa


def erro_transitorio(e: Exception) -> bool:
    """Falhas temporárias: vale tentar de novo ou trocar de modelo."""
    if isinstance(e, errors.APIError):
        return e.code in CODIGOS_TRANSITORIOS
    return isinstance(e, (httpx.TimeoutException, httpx.ConnectError))


@lru_cache(maxsize=1)
def cliente() -> genai.Client:
    # Por padrão o SDK NÃO repete chamadas que falham. Aqui ele tenta até 3 vezes,
    # esperando ~2s, 4s... (com variação aleatória) entre as tentativas.
    # O timeout corta chamadas "penduradas": sob alta demanda, o servidor pode levar
    # dezenas de segundos só para devolver um 503.
    return genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=2.0,
                max_delay=20.0,
                http_status_codes=CODIGOS_TRANSITORIOS,
            )
        ),
    )


def carregar_prompt(nome: str) -> str:
    return (config.PROMPTS / nome).read_text(encoding="utf-8")