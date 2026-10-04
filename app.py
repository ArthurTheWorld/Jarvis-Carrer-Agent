"""Servidor do Jarvis no WhatsApp (para quando a conta da Meta for liberada).

    uvicorn app:app --port 8000
"""
import json
import logging
import os
from collections import deque

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

import nucleo
import whatsapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis.whatsapp")

app = FastAPI()
_processadas: deque = deque(maxlen=500)  # a Meta pode reenviar a mesma mensagem


@app.get("/webhook")
def verificar(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == os.getenv("WHATSAPP_VERIFY_TOKEN"):
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(status_code=403)


@app.post("/webhook")
async def receber(request: Request, tarefas: BackgroundTasks):
    corpo = await request.body()
    if not whatsapp.assinatura_valida(corpo, request.headers.get("X-Hub-Signature-256", "")):
        log.warning("Assinatura inválida: requisição ignorada.")
        raise HTTPException(status_code=403)
    for msg in whatsapp.extrair_mensagens(json.loads(corpo)):
        tarefas.add_task(processar, msg)
    return Response(status_code=200)


def processar(msg: dict) -> None:
    if msg.get("id") in _processadas:
        return
    _processadas.append(msg.get("id"))

    remetente = msg.get("from", "")
    if not whatsapp.remetente_autorizado(remetente):
        log.warning("Mensagem de número não autorizado ignorada: %s", remetente)
        return

    def responder(texto: str) -> None:
        whatsapp.enviar_texto(remetente, texto)

    try:
        whatsapp.marcar_lida(msg["id"])
        tipo = msg.get("type")
        if tipo == "text":
            nucleo.tratar(responder, texto=msg["text"]["body"])
        elif tipo == "audio":
            audio, mime = whatsapp.baixar_midia(msg["audio"]["id"])
            nucleo.tratar(responder, audio=audio, mime=mime)
        else:
            responder("Por enquanto eu entendo mensagens de texto e áudio.")
    except Exception:
        log.exception("Falha ao processar mensagem")
