"""Jarvis no Telegram (long polling: não precisa de servidor público nem ngrok).

    python telegram_bot.py

Comandos: /voz on | /voz off | /publicar
Na primeira mensagem, o seu ID aparece no terminal. Coloque-o em
TELEGRAM_ALLOWED_IDS no .env e reinicie.
"""
import logging
import os
import time

import requests

import config  # noqa: F401  (carrega o .env)
import nucleo
import voz

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("jarvis.telegram")

TOKEN = os.environ["TELEGRAM_TOKEN"]
API = f"https://api.telegram.org/bot{TOKEN}"
ARQUIVOS = f"https://api.telegram.org/file/bot{TOKEN}"
LIMITE_TEXTO = 4000      # o Telegram aceita até 4096 caracteres por mensagem
LIMITE_LEGENDA = 1024    # legenda de áudio

PERMITIDOS = set()
for _item in os.getenv("TELEGRAM_ALLOWED_IDS", "").replace(" ", "").split(","):
    if _item.isdigit():
        PERMITIDOS.add(int(_item))
    elif _item:
        logging.warning("TELEGRAM_ALLOWED_IDS: valor ignorado (não é um ID numérico): %s", _item)

_opcoes = {
    "voz": os.getenv("JARVIS_VOZ", "on").lower() == "on",
    "legenda": os.getenv("JARVIS_LEGENDA", "on").lower() == "on",
}


def _api(metodo: str, **params) -> dict:
    r = requests.post(f"{API}/{metodo}", json=params, timeout=params.get("timeout", 0) + 30)
    dados = r.json()
    if not dados.get("ok"):
        raise RuntimeError(f"Telegram {metodo}: {dados.get('description')}")
    return dados["result"]


def enviar(chat_id: int, texto: str) -> None:
    for i in range(0, len(texto), LIMITE_TEXTO):
        _api("sendMessage", chat_id=chat_id, text=texto[i:i + LIMITE_TEXTO])


def enviar_voz(chat_id: int, texto: str) -> None:
    """Responde em áudio. Se o TTS falhar (cota, rede), cai para texto em vez de ficar em silêncio."""
    try:
        _api("sendChatAction", chat_id=chat_id, action="record_voice")
        audio = voz.sintetizar(texto)
    except Exception as e:
        log.warning("TTS falhou (%s). Enviando em texto.", e)
        enviar(chat_id, texto)
        return

    dados = {"chat_id": chat_id}
    legenda_cabe = len(texto) <= LIMITE_LEGENDA
    if _opcoes["legenda"] and legenda_cabe:
        dados["caption"] = texto
    r = requests.post(f"{API}/sendVoice", data=dados,
                      files={"voice": ("jarvis.ogg", audio, "audio/ogg")}, timeout=60)
    if not r.json().get("ok"):
        log.warning("sendVoice falhou: %s. Enviando em texto.", r.text[:200])
        enviar(chat_id, texto)
        return
    if _opcoes["legenda"] and not legenda_cabe:
        enviar(chat_id, texto)  # texto longo demais para legenda: vai como mensagem separada


def baixar_arquivo(file_id: str) -> bytes:
    caminho = _api("getFile", file_id=file_id)["file_path"]
    r = requests.get(f"{ARQUIVOS}/{caminho}", timeout=60)
    r.raise_for_status()
    return r.content


def processar(msg: dict) -> None:
    usuario = msg.get("from", {}).get("id")
    chat_id = msg["chat"]["id"]

    if usuario not in PERMITIDOS:
        log.warning("Mensagem ignorada de ID não autorizado: %s (%s). "
                    "Se for você, coloque esse número em TELEGRAM_ALLOWED_IDS no .env.",
                    usuario, msg.get("from", {}).get("first_name"))
        return

    def responder(texto: str, falar: bool = False) -> None:
        if falar and _opcoes["voz"]:
            enviar_voz(chat_id, texto)
        else:
            enviar(chat_id, texto)

    texto = (msg.get("text") or "").strip()
    if texto == "/start":
        responder("Jarvis online. Pode mandar texto ou áudio. Comandos: /voz on, /voz off, /publicar.")
        return
    if texto.lower() in ("/voz on", "/voz off"):
        _opcoes["voz"] = texto.lower().endswith("on")
        responder(f"Respostas em áudio {'ativadas' if _opcoes['voz'] else 'desativadas'}.")
        return

    _api("sendChatAction", chat_id=chat_id, action="typing")

    if texto:
        nucleo.tratar(responder, texto=texto)
    elif "voice" in msg or "audio" in msg:
        midia = msg.get("voice") or msg.get("audio")
        audio = baixar_arquivo(midia["file_id"])
        nucleo.tratar(responder, audio=audio, mime=midia.get("mime_type", "audio/ogg").split(";")[0])
    else:
        responder("Por enquanto eu entendo mensagens de texto e áudio.")


def main() -> None:
    eu = _api("getMe")
    log.info("Jarvis conectado como @%s. Voz: %s (%s). Aguardando mensagens (Ctrl+C para sair).",
             eu["username"], "on" if _opcoes["voz"] else "off", voz.NOME_VOZ)
    if not PERMITIDOS:
        log.warning("TELEGRAM_ALLOWED_IDS vazio: mande uma mensagem ao bot para descobrir o seu ID.")

    offset = None
    while True:
        try:
            atualizacoes = _api("getUpdates", timeout=50, offset=offset, allowed_updates=["message"])
        except requests.RequestException as e:
            log.warning("Falha de rede (%s). Tentando de novo em 5s.", e)
            time.sleep(5)
            continue
        except RuntimeError as e:
            log.error("%s", e)
            time.sleep(5)
            continue

        for upd in atualizacoes:
            offset = upd["update_id"] + 1  # confirma: o Telegram não reenvia esta atualização
            if "message" in upd:
                try:
                    processar(upd["message"])
                except Exception:
                    log.exception("Falha ao processar mensagem")


if __name__ == "__main__":
    main()
