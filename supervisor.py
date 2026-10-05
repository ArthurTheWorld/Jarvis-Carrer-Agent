"""Mantém o Jarvis rodando em segundo plano no Windows.

Iniciado pelo Agendador de Tarefas com o pythonw.exe (sem janela). Ele:
- roda o telegram_bot.py sem abrir janela de console;
- reinicia o bot se ele cair (queda de internet, erro inesperado);
- grava tudo em logs/jarvis.log;
- impede duas cópias ao mesmo tempo (o Telegram não aceita dois bots puxando mensagens).

Para ver o que está acontecendo, abra logs/jarvis.log.
Para parar: powershell -File parar_jarvis.ps1
"""
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
LOGS = RAIZ / "logs"
ARQUIVO_LOG = LOGS / "jarvis.log"
TAMANHO_MAXIMO = 5 * 1024 * 1024  # 5 MB: acima disso, o log atual vira jarvis.log.old
ESPERA_REINICIO = 15  # segundos
PORTA_TRAVA = 47201   # usada só como trava de "uma instância por vez"


def python_do_venv() -> str:
    """python.exe ao lado do pythonw.exe que rodou este script (o do .venv)."""
    exe = Path(sys.executable)
    candidato = exe.with_name("python.exe")
    return str(candidato if candidato.exists() else exe)


def girar_log() -> None:
    if ARQUIVO_LOG.exists() and ARQUIVO_LOG.stat().st_size > TAMANHO_MAXIMO:
        antigo = ARQUIVO_LOG.with_suffix(".log.old")
        antigo.unlink(missing_ok=True)
        ARQUIVO_LOG.rename(antigo)


def main() -> None:
    trava = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        trava.bind(("127.0.0.1", PORTA_TRAVA))
    except OSError:
        return  # já existe um supervisor rodando

    LOGS.mkdir(exist_ok=True)
    ambiente = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    sem_janela = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    while True:
        girar_log()
        with open(ARQUIVO_LOG, "a", encoding="utf-8") as log:
            log.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} Iniciando o Jarvis ===\n")
            log.flush()
            processo = subprocess.run(
                [python_do_venv(), "telegram_bot.py"],
                cwd=RAIZ, env=ambiente, stdout=log, stderr=subprocess.STDOUT,
                creationflags=sem_janela,
            )
            log.write(f"=== {datetime.now():%Y-%m-%d %H:%M:%S} O Jarvis parou (código {processo.returncode}). "
                      f"Reiniciando em {ESPERA_REINICIO}s ===\n")
        time.sleep(ESPERA_REINICIO)


if __name__ == "__main__":
    main()