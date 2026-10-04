"""Publicação no LinkedIn pela API oficial (produto "Share on LinkedIn").

IMPORTANTE: nada deste módulo é exposto ao Gemini como ferramenta. Publicar é a
única ação irreversível do Jarvis, por isso só acontece por um comando explícito
do Gustavo (/publicar), executado por código determinístico.
"""
import json
import os
import re
import time
from datetime import date

import requests

import config

TOKEN_PATH = config.RAIZ / "credenciais" / "linkedin_token.json"
URL_POSTS = "https://api.linkedin.com/rest/posts"

# Caracteres reservados do formato "little text" usado no campo commentary.
# Sem escape, o LinkedIn rejeita o post ou corta o texto no primeiro caractere reservado.
_RESERVADOS = set("\\|{}@[]()<>#*_~")


def _versao_api() -> str:
    """Versão da API no formato AAAAMM. Use LINKEDIN_VERSION no .env para fixar uma versão.

    Por padrão usa a de dois meses atrás: versões novas saem mensalmente e as antigas
    são desativadas após cerca de um ano.
    """
    if os.getenv("LINKEDIN_VERSION"):
        return os.environ["LINKEDIN_VERSION"]
    hoje = date.today()
    mes = hoje.month - 2
    ano = hoje.year + (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    return f"{ano}{mes:02d}"


def _escapar(texto: str) -> str:
    return "".join(f"\\{c}" if c in _RESERVADOS else c for c in texto)


def formatar_commentary(texto: str) -> str:
    """Escapa o texto e transforma #Termo em hashtag de verdade (clicável)."""
    partes = re.split(r"(#\w+)", texto)
    saida = []
    for parte in partes:
        if re.fullmatch(r"#\w+", parte):
            saida.append("{hashtag|\\#|" + _escapar(parte[1:]) + "}")
        else:
            saida.append(_escapar(parte))
    return "".join(saida)


def carregar_token() -> dict | None:
    if not TOKEN_PATH.exists():
        return None
    return json.loads(TOKEN_PATH.read_text(encoding="utf-8"))


def dias_para_expirar() -> int | None:
    token = carregar_token()
    if token is None:
        return None
    return int((token["expira_em"] - time.time()) // 86400)


def montar_payload(texto: str, autor_urn: str) -> dict:
    return {
        "author": autor_urn,
        "commentary": formatar_commentary(texto),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def publicar(texto: str) -> dict:
    """Publica o texto no perfil do Gustavo. Retorna o URN do post criado."""
    token = carregar_token()
    if token is None:
        return {"ok": False, "erro": "Sem token do LinkedIn. Rode: python linkedin_auth.py"}
    if token["expira_em"] <= time.time():
        return {"ok": False, "erro": "Token do LinkedIn expirado. Rode: python linkedin_auth.py"}

    resp = requests.post(
        URL_POSTS,
        headers={
            "Authorization": f"Bearer {token['access_token']}",
            "LinkedIn-Version": _versao_api(),
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        },
        json=montar_payload(texto, token["autor_urn"]),
        timeout=30,
    )
    if resp.status_code == 201:
        urn = resp.headers.get("x-restli-id", "")
        return {"ok": True, "urn": urn, "url": f"https://www.linkedin.com/feed/update/{urn}/" if urn else None}
    return {"ok": False, "erro": f"HTTP {resp.status_code}: {resp.text[:500]}"}
