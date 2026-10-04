"""Claude (Anthropic) como última linha de reserva, quando os modelos do Google caem.

Limitação conhecida: a API do Claude não aceita áudio, então aqui só entra texto.
As ferramentas são as mesmas do Gemini: o schema é gerado a partir das mesmas
funções Python, então não há duas definições para manter sincronizadas.
"""
import json
import logging
import os

import anthropic
from google.genai import types

import config  # noqa: F401  (carrega o .env)

log = logging.getLogger("jarvis.claude")

MODELO = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
MAX_PASSOS = 8          # limite de rodadas de ferramenta por mensagem
MAX_HISTORICO = 20      # mensagens recentes levadas como contexto

_TIPOS = {"STRING": "string", "INTEGER": "integer", "NUMBER": "number",
          "BOOLEAN": "boolean", "OBJECT": "object", "ARRAY": "array"}


class Indisponivel(Exception):
    pass


def disponivel() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


_cliente = None


def _client() -> anthropic.Anthropic:
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic(max_retries=3)  # lê ANTHROPIC_API_KEY do ambiente
    return _cliente


# ---------- ferramentas: schema do Gemini → JSON Schema do Claude ----------

def _json_schema(s: types.Schema | None) -> dict:
    if s is None:
        return {"type": "object", "properties": {}}
    tipo = s.type.value if hasattr(s.type, "value") else str(s.type)
    saida: dict = {"type": _TIPOS.get(tipo, "string")}
    if s.description:
        saida["description"] = s.description
    if s.enum:
        saida["enum"] = list(s.enum)
    if s.properties:
        saida["properties"] = {k: _json_schema(v) for k, v in s.properties.items()}
    if s.required:
        saida["required"] = list(s.required)
    if s.items:
        saida["items"] = _json_schema(s.items)
    if saida["type"] == "object":
        saida.setdefault("properties", {})
    return saida


def _ferramentas_claude(funcoes) -> list[dict]:
    lista = []
    for f in funcoes:
        d = types.FunctionDeclaration.from_callable_with_api_option(callable=f, api_option="GEMINI_API")
        lista.append({"name": d.name, "description": d.description or "", "input_schema": _json_schema(d.parameters)})
    return lista


# ---------- histórico: conversa do Gemini → mensagens do Claude ----------

def _historico(conteudos) -> list[dict]:
    """Leva só o texto das últimas mensagens (chamadas de ferramenta e áudio ficam de fora)."""
    msgs: list[dict] = []
    for c in list(conteudos)[-MAX_HISTORICO:]:
        papel = {"user": "user", "model": "assistant"}.get(c.role)
        texto = "\n".join(p.text for p in (c.parts or []) if getattr(p, "text", None))
        if not papel or not texto.strip():
            continue
        if msgs and msgs[-1]["role"] == papel:  # o Claude exige alternância user/assistant
            msgs[-1]["content"] += "\n\n" + texto
        else:
            msgs.append({"role": papel, "content": texto})
    while msgs and msgs[0]["role"] != "user":
        msgs.pop(0)
    return msgs


# ---------- conversa com ferramentas ----------

def responder(sistema: str, historico_gemini, mensagem: str, funcoes) -> str:
    por_nome = {f.__name__: f for f in funcoes}
    msgs = _historico(historico_gemini)
    if msgs and msgs[-1]["role"] == "user":
        msgs[-1]["content"] += "\n\n" + mensagem
    else:
        msgs.append({"role": "user", "content": mensagem})

    ferramentas = _ferramentas_claude(funcoes)
    try:
        for _ in range(MAX_PASSOS):
            resp = _client().messages.create(
                model=MODELO, max_tokens=1024, system=sistema, tools=ferramentas, messages=msgs,
            )
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text").strip() or "(sem resposta em texto)"

            msgs.append({"role": "assistant", "content": resp.content})
            resultados = []
            for bloco in resp.content:
                if bloco.type != "tool_use":
                    continue
                funcao = por_nome.get(bloco.name)
                try:
                    resultado = funcao(**bloco.input) if funcao else {"ok": False, "erro": f"Ferramenta desconhecida: {bloco.name}"}
                except Exception as e:  # ex.: rascunhar_post depende do Gemini, que pode estar fora
                    resultado = {"ok": False, "erro": f"{type(e).__name__}: {e}"}
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloco.id,
                    "content": json.dumps(resultado, ensure_ascii=False, default=str),
                })
            msgs.append({"role": "user", "content": resultados})
        return "Precisei interromper: a tarefa exigiu passos demais. Pode reformular em partes menores?"
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        log.warning("Claude indisponível: %s", e)
        raise Indisponivel(str(e)) from e
