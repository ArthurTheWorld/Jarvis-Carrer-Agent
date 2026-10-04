"""Configuração central do Jarvis. Tudo que muda entre ambientes vem do .env."""
import os
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")


def _caminho(valor: str) -> Path:
    """Aceita caminho absoluto ou relativo à raiz do projeto."""
    p = Path(valor)
    return p if p.is_absolute() else RAIZ / p


GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODELO = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
# Usado quando o modelo principal está sobrecarregado. Deixe vazio para desativar.
MODELO_RESERVA = os.getenv("GEMINI_MODEL_RESERVA", "gemini-2.5-flash-lite")

GOOGLE_CREDENTIALS = _caminho(os.environ["GOOGLE_CREDENTIALS"])
PLANILHA_ID = os.environ["PLANILHA_ID"]

FUSO = ZoneInfo("America/Sao_Paulo")
PROMPTS = RAIZ / "prompts"
POSTS_APROVADOS = RAIZ / "posts_aprovados.jsonl"
POSTS_PUBLICADOS = RAIZ / "posts_publicados.jsonl"


def agora() -> datetime:
    return datetime.now(FUSO)


def hoje() -> date:
    return agora().date()
