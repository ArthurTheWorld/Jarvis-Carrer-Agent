"""Acesso ao Google Sheets e regras de posição da planilha.

Toda a lógica de "onde fica cada coisa" na planilha mora aqui. Se o layout
mudar, só este arquivo muda.
"""
from datetime import date, timedelta
from functools import lru_cache

import gspread
from gspread.utils import ValueInputOption, ValueRenderOption

import config

EPOCA_PLANILHA = date(1899, 12, 30)  # dia 0 do número serial de datas
PRIMEIRA_LINHA_REGISTRO = 5
TOTAL_DIAS = 84  # 12 semanas
TOTAL_SEMANAS = 12


class ForaDoIntervalo(ValueError):
    pass


@lru_cache(maxsize=1)
def _planilha() -> gspread.Spreadsheet:
    gc = gspread.service_account(filename=str(config.GOOGLE_CREDENTIALS))
    return gc.open_by_key(config.PLANILHA_ID)


@lru_cache(maxsize=None)
def aba(nome: str) -> gspread.Worksheet:
    return _planilha().worksheet(nome)


def ler(nome_aba: str, intervalo: str) -> list:
    """Lê uma linha de valores brutos (números de verdade, não texto formatado)."""
    valores = aba(nome_aba).get(intervalo, value_render_option=ValueRenderOption.unformatted)
    return valores[0] if valores else []


def escrever(nome_aba: str, intervalo: str, linha: list) -> None:
    aba(nome_aba).update(
        range_name=intervalo, values=[linha], value_input_option=ValueInputOption.user_entered
    )


def serial_para_data(valor) -> date:
    return EPOCA_PLANILHA + timedelta(days=int(valor))


def data_inicio() -> date:
    return serial_para_data(ler("Config", "C4")[0])


def linha_do_dia(dia: date) -> int:
    """Linha da aba Registro Diário para uma data. Uma conta, nenhuma busca."""
    inicio = data_inicio()
    delta = (dia - inicio).days
    if not 0 <= delta < TOTAL_DIAS:
        fim = inicio + timedelta(days=TOTAL_DIAS - 1)
        raise ForaDoIntervalo(
            f"A data {dia:%d/%m/%Y} está fora do período da planilha "
            f"({inicio:%d/%m/%Y} a {fim:%d/%m/%Y})."
        )
    return PRIMEIRA_LINHA_REGISTRO + delta


def semana_de(dia: date) -> int:
    return (dia - data_inicio()).days // 7 + 1
