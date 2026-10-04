"""Lógica de atendimento compartilhada por todos os canais (Telegram, WhatsApp, ...).

Cada canal só sabe receber e enviar mensagens. Tudo o que o Jarvis decide fica
aqui, então trocar ou somar canais não muda o comportamento dele.
"""
import threading
from typing import Callable

from google.genai import errors

from agente import AcoesSemResposta, Jarvis, ModelosIndisponiveis
from llm import CODIGOS_TRANSITORIOS
from tools import conteudo, linkedin

Enviar = Callable[..., None]  # enviar(texto, falar=False)

_jarvis: Jarvis | None = None
_trava = threading.Lock()       # uma mensagem por vez: o agente tem estado de conversa
_confirmacao = {"post": None}   # post aguardando o "SIM" do /publicar


def _agente() -> Jarvis:
    global _jarvis
    if _jarvis is None:
        _jarvis = Jarvis()
    return _jarvis


def tratar(enviar: Enviar, texto: str | None = None,
           audio: bytes | None = None, mime: str = "audio/ogg") -> None:
    with _trava:
        try:
            _tratar(enviar, texto.strip() if texto else None, audio, mime)
        except AcoesSemResposta as e:
            for bloco in conteudo.consumir_exibicao():
                enviar(bloco)
            enviar(_mensagem_acoes(e.execucoes))
        except ModelosIndisponiveis:
            enviar("O Gemini está sobrecarregado agora. Tentei várias vezes, inclusive com o modelo reserva, "
                   "e nada foi alterado. Pode reenviar em alguns minutos.")
        except errors.APIError as e:
            if e.code in CODIGOS_TRANSITORIOS:
                enviar(f"O Gemini está instável agora (erro {e.code}). Nada foi alterado. Pode reenviar em alguns minutos.")
            else:
                enviar(f"Erro do Gemini ({e.code}): {e.message}")
                raise
        except Exception as e:  # o erro vira mensagem, em vez de silêncio
            enviar(f"Tive um problema ao processar: {type(e).__name__}: {e}")
            raise


def _mensagem_acoes(execucoes) -> str:
    """Resposta montada por código quando o modelo caiu depois de agir."""
    linhas = []
    for nome, _args, r in execucoes:
        if nome == "registrar_dia":
            itens = ", ".join(f"{k}: {v}" for k, v in r.get("alterados", {}).items())
            linhas.append(f"- Registrado em {r.get('data')}: {itens}")
        elif nome in ("rascunhar_post", "ajustar_post"):
            linhas.append("- Rascunho do post gerado (mensagem acima)")
        elif nome == "aprovar_post":
            linhas.append("- Post aprovado e salvo. Envie /publicar quando quiser.")
        elif nome == "descartar_post":
            linhas.append("- Rascunho descartado")
    return ("O modelo ficou indisponível antes de eu terminar a resposta, mas estas ações já foram feitas:\n"
            + "\n".join(linhas)
            + "\n\nNão reenvie a mesma mensagem, para não duplicar. Pode seguir normalmente.")


def _tratar(enviar: Enviar, texto: str | None, audio: bytes | None, mime: str) -> None:
    # 1) Confirmação de publicação: 100% determinística, o modelo não participa.
    if _confirmacao["post"] is not None:
        post, _confirmacao["post"] = _confirmacao["post"], None
        if texto and texto.upper() == "SIM":
            r = linkedin.publicar(post["texto"])
            if r["ok"]:
                conteudo.marcar_publicado(post["id"], r["urn"])
                enviar(f"Publicado no LinkedIn: {r.get('url') or r['urn']}")
            else:
                enviar(f"Falha ao publicar: {r['erro']}")
        else:
            enviar("Publicação cancelada. O post continua aprovado; envie /publicar quando quiser.")
        return

    if texto and texto.lower() == "/publicar":
        post = conteudo.post_pendente_publicacao()
        if post is None:
            enviar("Nenhum post aprovado aguardando publicação.")
            return
        aviso = ""
        dias = linkedin.dias_para_expirar()
        if dias is None or dias < 0:
            enviar("O login do LinkedIn não está ativo. Rode no computador: python linkedin_auth.py")
            return
        if dias <= 7:
            aviso = f"\n\n(Atenção: o login do LinkedIn expira em {dias} dia(s). Rode python linkedin_auth.py.)"
        _confirmacao["post"] = post
        enviar(f"VAI SER PUBLICADO:\n\n{post['texto']}\n\nResponda SIM para publicar. Qualquer outra resposta cancela.{aviso}")
        return

    # 2) Conversa normal com o agente.
    resposta = _agente().responder(texto=texto, audio=audio, mime=mime)
    for bloco in conteudo.consumir_exibicao():
        enviar(bloco)                 # rascunhos sempre em texto: você precisa ler e copiar
    enviar(resposta, falar=True)      # só a resposta do agente pode virar áudio