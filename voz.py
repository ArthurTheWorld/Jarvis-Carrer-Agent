"""Voz do Jarvis: texto → áudio com o TTS do Gemini → OGG/Opus (formato de nota de voz).

A voz é uma das vozes prontas do Gemini, com um estilo de fala definido por
instrução. Não é cópia da voz de nenhuma pessoa real.
"""
import io
import os

import av
from google.genai import types

import config  # noqa: F401  (carrega o .env)
from llm import cliente

MODELO_TTS = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
NOME_VOZ = os.getenv("JARVIS_VOZ_NOME", "Charon")
TAXA = 24000  # o TTS do Gemini devolve PCM 16 bits, mono, 24 kHz

ESTILO = (
    "Leia o texto a seguir em português do Brasil, com voz masculina calma, educada e "
    "levemente formal, ritmo tranquilo e dicção precisa, como um assistente executivo "
    "experiente e discreto. Leia exatamente o texto, sem acrescentar nada:"
)


def _pcm_para_ogg(pcm: bytes) -> bytes:
    buffer = io.BytesIO()
    with av.open(buffer, "w", format="ogg") as saida:
        stream = saida.add_stream("libopus", rate=TAXA)
        stream.layout = "mono"
        frame = av.AudioFrame(format="s16", layout="mono", samples=len(pcm) // 2)
        frame.sample_rate = TAXA
        frame.planes[0].update(pcm[: (len(pcm) // 2) * 2])
        for pacote in stream.encode(frame):
            saida.mux(pacote)
        for pacote in stream.encode(None):
            saida.mux(pacote)
    return buffer.getvalue()


def sintetizar(texto: str) -> bytes:
    """Gera a nota de voz (OGG/Opus) para o texto."""
    resp = cliente().models.generate_content(
        model=MODELO_TTS,
        contents=f"{ESTILO}\n\n{texto}",
        config=types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=NOME_VOZ)
                )
            ),
        ),
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    return _pcm_para_ogg(pcm)