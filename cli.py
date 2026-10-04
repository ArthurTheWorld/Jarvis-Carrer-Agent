"""Interface de terminal do Jarvis.

Uso:  python cli.py
      Texto normal → conversa
      /audio caminho/do/arquivo.ogg → envia um áudio
      /publicar → publica no LinkedIn o último post aprovado (pede confirmação)
      sair → encerra
"""
from pathlib import Path

from agente import Jarvis
from tools import conteudo, linkedin

MIMES = {".ogg": "audio/ogg", ".opus": "audio/ogg", ".mp3": "audio/mp3",
         ".m4a": "audio/mp4", ".wav": "audio/wav"}


def avisar_token() -> None:
    dias = linkedin.dias_para_expirar()
    if dias is None:
        print("[LinkedIn] Sem login. Para publicar, rode antes: python linkedin_auth.py")
    elif dias < 0:
        print("[LinkedIn] Token expirado. Rode: python linkedin_auth.py")
    elif dias <= 7:
        print(f"[LinkedIn] Token expira em {dias} dia(s). Rode em breve: python linkedin_auth.py")


def comando_publicar() -> None:
    """Fluxo determinístico: o modelo não participa da decisão de publicar."""
    post = conteudo.post_pendente_publicacao()
    if post is None:
        print("\nNenhum post aprovado aguardando publicação.")
        return
    print("\n──────── VAI SER PUBLICADO ────────")
    print(post["texto"])
    print("───────────────────────────────────")
    if input("Publicar agora no LinkedIn? Digite SIM para confirmar: ").strip() != "SIM":
        print("Publicação cancelada. O post continua aprovado e pendente.")
        return
    resultado = linkedin.publicar(post["texto"])
    if resultado["ok"]:
        conteudo.marcar_publicado(post["id"], resultado["urn"])
        print(f"Publicado! {resultado.get('url') or resultado['urn']}")
    else:
        print(f"Falha ao publicar: {resultado['erro']}")


def main() -> None:
    jarvis = Jarvis()
    print("Jarvis online. Texto para conversar, '/audio caminho' para áudio, '/publicar', 'sair'.")
    avisar_token()
    while True:
        entrada = input("\nVocê: ").strip()
        if not entrada:
            continue
        if entrada.lower() in ("sair", "exit", "quit"):
            break
        if entrada == "/publicar":
            comando_publicar()
            continue
        try:
            if entrada.startswith("/audio "):
                caminho = Path(entrada[len("/audio "):].strip().strip('"'))
                mime = MIMES.get(caminho.suffix.lower())
                if mime is None:
                    print(f"Formato não suportado: {caminho.suffix}")
                    continue
                resposta = jarvis.responder(audio=caminho.read_bytes(), mime=mime)
            else:
                resposta = jarvis.responder(texto=entrada)
        except FileNotFoundError as e:
            print(f"Arquivo não encontrado: {e.filename}")
            continue
        except Exception as e:  # mantém a sessão viva para você ver o erro e seguir
            print(f"[erro] {type(e).__name__}: {e}")
            continue

        for bloco in conteudo.consumir_exibicao():
            print(f"\n{bloco}")
        print(f"\nJarvis: {resposta}")


if __name__ == "__main__":
    main()
