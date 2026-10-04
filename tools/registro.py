"""Ferramentas de registro diário e acompanhamento semanal.

As docstrings são lidas pelo Gemini para decidir quando e como chamar cada
função: elas fazem parte do comportamento do agente, não só da documentação.
"""
from datetime import date
from typing import Optional

import config
import planilha
from planilha import ForaDoIntervalo

ABA_REGISTRO = "Registro Diário"
ABA_METAS = "Metas Semanais"

# Ordem das colunas D:M da aba Registro Diário
CAMPOS = [
    "rotina_feita", "posts", "convites", "convites_recrutadores", "convites_aceitos",
    "comentarios", "acoes_relacionamento", "conversas_iniciadas", "ingles_minutos",
    "observacoes",
]
NUMERICOS = CAMPOS[1:9]


def _como_int(valor) -> int:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0


def _ler_dia(linha: int) -> dict:
    valores = planilha.ler(ABA_REGISTRO, f"D{linha}:M{linha}")
    valores += [""] * (len(CAMPOS) - len(valores))
    return dict(zip(CAMPOS, valores))


def registrar_dia(
    data: str,
    modo: str = "somar",
    rotina_feita: Optional[bool] = None,
    posts: Optional[int] = None,
    convites: Optional[int] = None,
    convites_recrutadores: Optional[int] = None,
    convites_aceitos: Optional[int] = None,
    comentarios: Optional[int] = None,
    acoes_relacionamento: Optional[int] = None,
    conversas_iniciadas: Optional[int] = None,
    ingles_minutos: Optional[int] = None,
    observacoes: Optional[str] = None,
) -> dict:
    """Registra atividades de LinkedIn e inglês de um dia na planilha de acompanhamento.

    Use quando o Gustavo relatar o que fez em um dia (convites enviados, comentários,
    posts, conversas, prática de inglês etc.). Informe SOMENTE os campos que ele citou;
    campos não citados devem ficar de fora e não são alterados na planilha.
    Nunca estime ou invente quantidades: se ele não disser o número, pergunte antes.

    Args:
        data: Data das atividades no formato AAAA-MM-DD. Resolva "hoje", "ontem" etc. a partir da data atual informada no contexto.
        modo: "somar" (padrão) acrescenta aos valores já registrados no dia, para relatos como "mandei mais 10 convites". "corrigir" substitui os valores, apenas quando ele indicar correção explícita ("na verdade foram 20", "errei", "corrige").
        rotina_feita: True se ele fez a rotina de 15 minutos no dia; False se disser que não fez.
        posts: Quantidade de posts publicados.
        convites: Total de convites de conexão enviados (inclui os enviados a recrutadores).
        convites_recrutadores: Quantos dos convites enviados foram para recrutadores. É um subconjunto de convites, nunca maior que ele.
        convites_aceitos: Quantos convites foram aceitos.
        comentarios: Comentários com contribuição real feitos em posts.
        acoes_relacionamento: Ações de relacionamento: responder mensagem, agradecer, retomar ou nutrir uma conexão.
        conversas_iniciadas: Conversas novas iniciadas com contatos.
        ingles_minutos: Minutos de prática de inglês.
        observacoes: Nota livre curta sobre o dia, apenas se ele pedir para anotar algo.

    Returns:
        Dicionário com os valores finais gravados no dia, ou com o erro ocorrido.
    """
    if modo not in ("somar", "corrigir"):
        return {"ok": False, "erro": "modo deve ser 'somar' ou 'corrigir'."}

    informados = {
        "rotina_feita": rotina_feita, "posts": posts, "convites": convites,
        "convites_recrutadores": convites_recrutadores, "convites_aceitos": convites_aceitos,
        "comentarios": comentarios, "acoes_relacionamento": acoes_relacionamento,
        "conversas_iniciadas": conversas_iniciadas, "ingles_minutos": ingles_minutos,
        "observacoes": observacoes,
    }
    informados = {k: v for k, v in informados.items() if v is not None}
    if not informados:
        return {"ok": False, "erro": "Nenhuma atividade informada para registrar."}

    negativos = [k for k in NUMERICOS if k in informados and informados[k] < 0]
    if negativos:
        return {"ok": False, "erro": f"Valores negativos não são permitidos: {negativos}."}

    try:
        dia = date.fromisoformat(data)
        linha = planilha.linha_do_dia(dia)
    except ForaDoIntervalo as e:
        return {"ok": False, "erro": str(e)}
    except ValueError:
        return {"ok": False, "erro": f"Data inválida: {data}. Use AAAA-MM-DD."}

    atual = _ler_dia(linha)
    novo = dict(atual)

    for campo, valor in informados.items():
        if campo == "rotina_feita":
            novo[campo] = "S" if valor else "N"
        elif campo == "observacoes":
            anterior = str(atual.get(campo) or "").strip()
            novo[campo] = f"{anterior} | {valor}" if (modo == "somar" and anterior) else valor
        elif modo == "somar":
            novo[campo] = _como_int(atual.get(campo)) + int(valor)
        else:
            novo[campo] = int(valor)

    avisos = []
    if _como_int(novo["convites_recrutadores"]) > _como_int(novo["convites"]):
        avisos.append("Convites para recrutadores ficaram maiores que o total de convites do dia. Confirme os números.")

    planilha.escrever(ABA_REGISTRO, f"D{linha}:M{linha}", [novo[c] for c in CAMPOS])

    return {
        "ok": True,
        "data": dia.isoformat(),
        "modo": modo,
        "alterados": {k: novo[k] for k in informados},
        "totais_do_dia": {k: novo[k] for k in CAMPOS if novo[k] not in ("", None)},
        "avisos": avisos,
    }


def consultar_dia(data: str) -> dict:
    """Mostra o que já está registrado na planilha para um dia.

    Use quando o Gustavo perguntar o que registrou em um dia, ou antes de uma correção
    se não estiver claro qual é o valor atual.

    Args:
        data: Data no formato AAAA-MM-DD.
    """
    try:
        dia = date.fromisoformat(data)
        linha = planilha.linha_do_dia(dia)
    except ForaDoIntervalo as e:
        return {"ok": False, "erro": str(e)}
    except ValueError:
        return {"ok": False, "erro": f"Data inválida: {data}. Use AAAA-MM-DD."}
    registrado = {k: v for k, v in _ler_dia(linha).items() if v not in ("", None)}
    return {"ok": True, "data": dia.isoformat(), "registrado": registrado or "Nada registrado neste dia."}


def _pct(valor) -> Optional[float]:
    return round(float(valor), 3) if isinstance(valor, (int, float)) else None


def resumo_semana(semana: Optional[int] = None) -> dict:
    """Retorna a performance de uma semana do desafio frente às metas.

    Use quando o Gustavo perguntar como está indo, como foi a semana, o que está
    atrasado ou onde deve focar. Traz realizado, meta e % da meta por comportamento,
    além de taxa de aceitação, % de convites para recrutadores, score e status.

    Args:
        semana: Número da semana do desafio (1 a 12). Omita para usar a semana atual.
    """
    try:
        if semana is None:
            semana = planilha.semana_de(config.hoje())
        semana = max(1, min(planilha.TOTAL_SEMANAS, int(semana)))
        linha = 4 + semana
        v = planilha.ler(ABA_METAS, f"A{linha}:T{linha}")
        m = planilha.ler(ABA_METAS, "A3:T3")
    except Exception as e:  # devolve o erro ao modelo em vez de derrubar a conversa
        return {"ok": False, "erro": f"Não foi possível ler a semana: {e}"}
    v += [""] * (20 - len(v))
    m += [""] * (20 - len(m))

    def bloco(i_real, i_pct):
        return {"realizado": v[i_real], "meta": m[i_real], "pct_meta": _pct(v[i_pct])}

    return {
        "ok": True,
        "semana": semana,
        "periodo": f"{planilha.serial_para_data(v[1]):%d/%m} a {planilha.serial_para_data(v[2]):%d/%m}",
        "semana_ainda_nao_comecou": v[18] in ("", None),
        "posts": bloco(3, 4),
        "convites": bloco(5, 6),
        "comentarios": bloco(9, 10),
        "acoes_relacionamento": bloco(11, 12),
        "dias_ingles": bloco(14, 15),
        "dias_rotina": bloco(16, 17),
        "pct_convites_recrutadores": {"realizado": _pct(v[7]), "meta": _pct(m[7])},
        "taxa_aceitacao": _pct(v[8]),
        "conversas_iniciadas": v[13],
        "score_semanal": _pct(v[18]),
        "status": v[19],
    }
