from pathlib import Path
import sys

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.actuarial.cashflow import inadimplencia_por_metodo, montar_fluxo_caixa_mensal
from src.actuarial.metrics import (
    calcular_indicadores_atuariais,
    montar_comparativo_indicadores,
)
from src.actuarial.risk import (
    RiskScoreWeights,
    RiskSegmentationThresholds,
    aplicar_segmentacao_risco,
    ranking_prioridade_migracao_pix,
)
from src.actuarial.simulation import simular_pix_automatico
from src.data.loaders import carregar_arquivo_pagamentos, carregar_csv_local
from src.data.schema import REQUIRED_PAYMENT_COLUMNS, preparar_base_pagamentos


st.set_page_config(
    page_title="TCC Atuarial - Pix Automatico em Seguradoras",
    layout="wide",
)

px.defaults.template = "plotly_white"

TAXA_RECUPERACAO_PIX_PADRAO = 0.40
TAXA_CANCELAMENTO_INADIMPLENTES_PADRAO = 0.25
TAXA_DESCONTO_ANUAL_PADRAO = 0.10
PESOS_RISCO_PADRAO = RiskScoreWeights()
LIMITES_RISCO_PADRAO = RiskSegmentationThresholds()


def formatar_moeda(valor: float) -> str:
    texto = f"R$ {valor:,.2f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_moeda_compacta(valor: float) -> str:
    valor_abs = abs(valor)

    if valor_abs >= 1_000_000_000:
        texto = f"R$ {valor / 1_000_000_000:,.1f} bi"
    elif valor_abs >= 1_000_000:
        texto = f"R$ {valor / 1_000_000:,.1f} mi"
    elif valor_abs >= 1_000:
        texto = f"R$ {valor / 1_000:,.1f} mil"
    else:
        texto = f"R$ {valor:,.0f}"

    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor: float) -> str:
    return f"{valor:.2%}".replace(".", ",")


def formatar_percentual_compacto(valor: float) -> str:
    return f"{valor:.1%}".replace(".", ",")


def formatar_numero(valor: float) -> str:
    return f"{valor:,.0f}".replace(",", ".")


def formatar_dias_mercado(valor: float) -> str:
    dias = int(round(valor))
    unidade = "dia" if dias == 1 else "dias"

    return f"{dias} {unidade}"


def formatar_decimal(valor: float) -> str:
    return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_valor_indicador(indicador: str, valor: float) -> str:
    if "Taxa" in indicador or "Persistencia" in indicador:
        return formatar_percentual(valor)

    if "Atraso" in indicador:
        return formatar_dias_mercado(valor)

    if "Cancelamentos" in indicador:
        return formatar_numero(valor)

    return formatar_moeda(valor)


def montar_comparativo_formatado(comparativo: pd.DataFrame) -> pd.DataFrame:
    exibicao = comparativo.copy()
    exibicao = exibicao.rename(
        columns={
            "Cenario atual": "Carteira atual",
            "Cenário atual": "Carteira atual",
            "Cenario com Pix Automatico": "Estimativa com Pix Automatico",
            "Cenário com Pix Automático": "Estimativa com Pix Automatico",
        }
    )

    for coluna in ["Carteira atual", "Estimativa com Pix Automatico", "Variacao"]:
        if coluna not in exibicao.columns:
            continue

        exibicao[coluna] = exibicao.apply(
            lambda row: formatar_valor_indicador(row["Indicador"], row[coluna]),
            axis=1,
        )

    return exibicao


def carregar_base(fonte_dados: str, uploaded_file) -> tuple[pd.DataFrame | None, str]:
    if fonte_dados == "Upload de arquivo":
        if uploaded_file is None:
            return None, "Aguardando upload de CSV ou Excel."

        return carregar_arquivo_pagamentos(uploaded_file), uploaded_file.name

    caminho_base = ROOT_DIR / "data" / "pagamentos.csv"

    if not caminho_base.exists():
        return None, "Base sintetica local nao encontrada em data/pagamentos.csv."

    return carregar_csv_local(caminho_base), "data/pagamentos.csv"


def render_metric_card(label: str, valor: str, delta: str | None = None, positivo: bool = True):
    delta_html = ""

    if delta:
        delta_classe = "positivo" if positivo else "negativo"
        seta = "&uarr;" if positivo else "&darr;"
        delta_html = f'<div class="metric-delta {delta_classe}">{seta} {delta}</div>'

    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{valor}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def gerar_diagnostico_automatico(
    indicadores_atual: dict[str, float],
    indicadores_pix: dict[str, float],
    inadimplencia_metodo: pd.DataFrame,
    ranking_prioridade: pd.DataFrame,
) -> pd.DataFrame:
    premio_recuperado = indicadores_pix["premio_recuperado_pix"]
    reducao_inadimplencia_valor = (
        indicadores_atual["taxa_inadimplencia_valor"]
        - indicadores_pix["taxa_inadimplencia_valor"]
    )
    ganho_vp = (
        indicadores_pix["valor_presente_recebimentos"]
        - indicadores_atual["valor_presente_recebimentos"]
    )
    cancelamentos_evitados = (
        indicadores_atual["cancelamentos_estimados"]
        - indicadores_pix["cancelamentos_estimados"]
    )

    achados = [
        {
            "Achado": "Recuperação potencial",
            "Leitura para decisão": (
                f"O Pix Automático recupera {formatar_moeda(premio_recuperado)} "
                "do prêmio em aberto, preservando o prêmio esperado da carteira."
            ),
        },
        {
            "Achado": "Inadimplência por valor",
            "Leitura para decisão": (
                "A estimativa reduz a inadimplência por valor em "
                f"{formatar_percentual(reducao_inadimplencia_valor)} frente à carteira atual."
            ),
        },
        {
            "Achado": "Persistência estimada",
            "Leitura para decisão": (
                "A menor inadimplência reduz cancelamentos estimados em "
                f"{formatar_numero(cancelamentos_evitados)} cobranças da carteira."
            ),
        },
        {
            "Achado": "Valor presente",
            "Leitura para decisão": (
                "O valor presente dos recebimentos aumenta em "
                f"{formatar_moeda(ganho_vp)}."
            ),
        },
    ]

    if not inadimplencia_metodo.empty:
        metodo_critico = inadimplencia_metodo.iloc[0]
        achados.append(
            {
                "Achado": "Método mais sensível",
                "Leitura para decisão": (
                    f"{metodo_critico['metodo_pagamento']} apresenta a maior "
                    "inadimplência por valor entre os métodos de cobrança."
                ),
            }
        )

    if not ranking_prioridade.empty:
        prioridade = ranking_prioridade.iloc[0]
        partes_segmento = []

        if "ramo" in ranking_prioridade.columns:
            partes_segmento.append(str(prioridade["ramo"]))

        partes_segmento.extend(
            [
                str(prioridade["segmento_risco"]),
                str(prioridade["metodo_pagamento"]),
            ]
        )
        achados.append(
            {
                "Achado": "Prioridade de migração",
                "Leitura para decisão": (
                    "O grupo com maior prioridade atuarial é "
                    f"{' | '.join(partes_segmento)}, com recuperação potencial de "
                    f"{formatar_moeda(prioridade['recuperacao_potencial_pix'])}."
                ),
            }
        )

    return pd.DataFrame(achados)


st.markdown(
    """
    <style>
        .project-header {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 8px;
            padding: 22px 24px;
            margin-bottom: 20px;
            background:
                linear-gradient(135deg, rgba(47, 93, 124, 0.18), rgba(47, 125, 91, 0.14)),
                rgba(15, 23, 42, 0.28);
        }

        .project-kicker {
            color: rgba(226, 232, 240, 0.74);
            font-size: 0.78rem;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 8px;
        }

        .project-title {
            color: #f8fafc;
            font-size: 2.05rem;
            font-weight: 760;
            line-height: 1.12;
            margin-bottom: 8px;
        }

        .project-subtitle {
            color: rgba(226, 232, 240, 0.82);
            font-size: 1rem;
            line-height: 1.48;
            max-width: 920px;
            margin-bottom: 14px;
        }

        .method-strip {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }

        .method-chip {
            border: 1px solid rgba(148, 163, 184, 0.24);
            border-radius: 999px;
            padding: 4px 10px;
            color: rgba(226, 232, 240, 0.86);
            font-size: 0.78rem;
            font-weight: 650;
            background: rgba(15, 23, 42, 0.36);
        }

        .metric-card {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 8px;
            padding: 14px 16px;
            min-height: 104px;
            background: rgba(15, 23, 42, 0.34);
        }

        .metric-label {
            color: rgba(226, 232, 240, 0.78);
            font-size: 0.82rem;
            font-weight: 650;
            line-height: 1.2;
            margin-bottom: 8px;
        }

        .metric-value {
            color: #f8fafc;
            font-size: 1.7rem;
            font-weight: 720;
            line-height: 1.1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .metric-delta {
            display: inline-flex;
            align-items: center;
            margin-top: 10px;
            padding: 3px 8px;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 650;
        }

        .metric-delta.positivo {
            color: #22c55e;
            background: rgba(34, 197, 94, 0.14);
        }

        .metric-delta.negativo {
            color: #f87171;
            background: rgba(248, 113, 113, 0.14);
        }
    </style>

    <section class="project-header">
        <div class="project-kicker">Trabalho de Conclusão de Curso | Ciências Atuariais</div>
        <div class="project-title">Pix Automático em Seguradoras</div>
        <div class="project-subtitle">
            Ferramenta atuarial de apoio à decisão para avaliar recuperação de prêmio inadimplente,
            persistência de carteira, fluxo de caixa e valor presente dos recebimentos.
        </div>
        <div class="method-strip">
            <span class="method-chip">Prêmio esperado</span>
            <span class="method-chip">Inadimplência por valor</span>
            <span class="method-chip">Persistência estimada</span>
            <span class="method-chip">Score de risco</span>
            <span class="method-chip">Valor presente</span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Base da carteira")

    fonte_dados = st.radio(
        "Fonte de dados",
        ["Base sintetica local", "Upload de arquivo"],
        index=0,
    )

    uploaded_file = None
    if fonte_dados == "Upload de arquivo":
        uploaded_file = st.file_uploader(
            "Base de pagamentos",
            type=["csv", "xlsx", "xls"],
        )

    st.divider()
    st.caption(
        "A metodologia considera recuperação de prêmio em aberto, sem criação "
        "de receita nova. Os indicadores são calculados automaticamente após a carga."
    )

taxa_recuperacao_pix = TAXA_RECUPERACAO_PIX_PADRAO
taxa_cancelamento = TAXA_CANCELAMENTO_INADIMPLENTES_PADRAO
taxa_desconto_anual = TAXA_DESCONTO_ANUAL_PADRAO
pesos_risco = PESOS_RISCO_PADRAO
limites_risco = LIMITES_RISCO_PADRAO
pesos_risco_normalizados = pesos_risco.normalizados()

with st.expander("Metodologia atuarial aplicada", expanded=False):
    st.markdown(
        """
        A ferramenta considera que o Pix Automático não cria prêmio novo. A estimativa
        recupera parte do prêmio inadimplente já esperado pela seguradora.

        **Prêmio esperado - prêmio inadimplente + prêmio recuperado com Pix = prêmio recebido estimado.**

        Quando a base não possui `valor_esperado`, a aplicação infere esse valor pelo
        histórico pago da própria apólice ou pela média paga da carteira. Para bases
        reais, recomenda-se enviar `valor_esperado` explicitamente.
        """
    )

df_raw, origem = carregar_base(fonte_dados, uploaded_file)

if df_raw is None:
    st.info(origem)
    st.subheader("Schema mínimo esperado")
    st.dataframe(pd.DataFrame({"coluna_obrigatoria": REQUIRED_PAYMENT_COLUMNS}), hide_index=True)
    st.stop()

try:
    df_atual = preparar_base_pagamentos(df_raw)
except ValueError as exc:
    st.error(str(exc))
    st.subheader("Schema mínimo esperado")
    st.dataframe(pd.DataFrame({"coluna_obrigatoria": REQUIRED_PAYMENT_COLUMNS}), hide_index=True)
    st.stop()

if "valor_esperado" not in df_raw.columns:
    st.warning(
        "A base importada nao possui valor_esperado. O premio esperado foi inferido para manter compatibilidade com a base sintetica."
    )

df_atual = aplicar_segmentacao_risco(
    df_atual,
    pesos=pesos_risco,
    limites=limites_risco,
)
df_pix = simular_pix_automatico(df_atual, taxa_recuperacao_pix)
df_pix = aplicar_segmentacao_risco(
    df_pix,
    pesos=pesos_risco,
    limites=limites_risco,
)

indicadores_atual = calcular_indicadores_atuariais(
    df_atual,
    taxa_cancelamento,
    taxa_desconto_anual,
)
indicadores_pix = calcular_indicadores_atuariais(
    df_pix,
    taxa_cancelamento,
    taxa_desconto_anual,
)

comparativo = montar_comparativo_indicadores(indicadores_atual, indicadores_pix)
fluxo = montar_fluxo_caixa_mensal(df_atual, df_pix)
fluxo = fluxo.rename(columns={"cenario": "visao", "Cenário": "visao"})
inad_metodo = inadimplencia_por_metodo(df_atual)
ranking = ranking_prioridade_migracao_pix(df_atual, taxa_recuperacao_pix)
diagnostico = gerar_diagnostico_automatico(
    indicadores_atual,
    indicadores_pix,
    inad_metodo,
    ranking,
)

st.subheader("Resumo da carteira")
st.caption(
    f"Base analisada: {origem} | Cobranças avaliadas: {formatar_numero(len(df_atual))}"
)

st.subheader("Diagnóstico técnico-atuarial")
st.dataframe(diagnostico, use_container_width=True, hide_index=True)

linha1 = st.columns(5)
with linha1[0]:
    render_metric_card(
        "Prêmio esperado",
        formatar_moeda_compacta(indicadores_atual["premio_esperado"]),
    )
with linha1[1]:
    render_metric_card(
        "Recebido atual",
        formatar_moeda_compacta(indicadores_atual["premio_recebido"]),
    )
with linha1[2]:
    render_metric_card(
        "Recebido com Pix",
        formatar_moeda_compacta(indicadores_pix["premio_recebido"]),
        formatar_moeda_compacta(
            indicadores_pix["premio_recebido"] - indicadores_atual["premio_recebido"]
        ),
        positivo=True,
    )
with linha1[3]:
    render_metric_card(
        "Recuperado Pix",
        formatar_moeda_compacta(indicadores_pix["premio_recuperado_pix"]),
    )
with linha1[4]:
    render_metric_card(
        "VP dos recebimentos",
        formatar_moeda_compacta(indicadores_pix["valor_presente_recebimentos"]),
        formatar_moeda_compacta(
            indicadores_pix["valor_presente_recebimentos"]
            - indicadores_atual["valor_presente_recebimentos"]
        ),
        positivo=True,
    )

linha2 = st.columns(5)
with linha2[0]:
    reducao_inad_qtd = (
        indicadores_atual["taxa_inadimplencia_qtd"]
        - indicadores_pix["taxa_inadimplencia_qtd"]
    )
    render_metric_card(
        "Inadimplência qtd.",
        formatar_percentual_compacto(indicadores_pix["taxa_inadimplencia_qtd"]),
        formatar_percentual_compacto(reducao_inad_qtd),
        positivo=True,
    )
with linha2[1]:
    reducao_inad_valor = (
        indicadores_atual["taxa_inadimplencia_valor"]
        - indicadores_pix["taxa_inadimplencia_valor"]
    )
    render_metric_card(
        "Inadimplência valor",
        formatar_percentual_compacto(indicadores_pix["taxa_inadimplencia_valor"]),
        formatar_percentual_compacto(reducao_inad_valor),
        positivo=True,
    )
with linha2[2]:
    render_metric_card(
        "Persistência",
        formatar_percentual_compacto(indicadores_pix["persistencia_estimada"]),
        formatar_percentual_compacto(
            indicadores_pix["persistencia_estimada"]
            - indicadores_atual["persistencia_estimada"]
        ),
        positivo=True,
    )
with linha2[3]:
    render_metric_card(
        "Cancelamentos est.",
        formatar_numero(indicadores_pix["cancelamentos_estimados"]),
    )
with linha2[4]:
    render_metric_card(
        "Atraso médio",
        formatar_dias_mercado(indicadores_pix["atraso_medio"]),
    )

tab_resumo, tab_fluxo, tab_risco, tab_base = st.tabs(
    [
        "Indicadores atuariais",
        "Fluxo financeiro",
        "Priorização Pix",
        "Base analítica",
    ]
)

with tab_resumo:
    st.subheader("Indicadores atuariais da carteira")
    st.dataframe(
        montar_comparativo_formatado(comparativo),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Composição do prêmio")
    graf_premios = pd.DataFrame(
        {
            "Componente": [
                "Prêmio recebido atual",
                "Prêmio inadimplente atual",
                "Prêmio recuperado com Pix",
                "Prêmio ainda inadimplente",
            ],
            "Valor": [
                indicadores_atual["premio_recebido"],
                indicadores_atual["premio_inadimplente"],
                indicadores_pix["premio_recuperado_pix"],
                indicadores_pix["premio_inadimplente"],
            ],
        }
    )
    fig_premios = px.bar(
        graf_premios,
        x="Componente",
        y="Valor",
        color="Componente",
        color_discrete_sequence=["#2f5d7c", "#b94e48", "#2f7d5b", "#c08b2c"],
    )
    fig_premios.update_layout(showlegend=False, yaxis_title="Valor")
    st.plotly_chart(fig_premios, use_container_width=True)

with tab_fluxo:
    st.subheader("Fluxo financeiro mensal")
    fig_fluxo = px.line(
        fluxo,
        x="mes",
        y="premio_recebido",
        color="visao",
        markers=True,
        labels={
            "mes": "Mês de vencimento",
            "premio_recebido": "Prêmio recebido",
            "visao": "Visão da carteira",
        },
        color_discrete_sequence=["#2f5d7c", "#2f7d5b"],
    )
    st.plotly_chart(fig_fluxo, use_container_width=True)

    st.subheader("Inadimplência por método de cobrança")
    fig_metodo = px.bar(
        inad_metodo,
        x="metodo_pagamento",
        y="taxa_inadimplencia_valor",
        color="metodo_pagamento",
        labels={
            "metodo_pagamento": "Método de cobrança",
            "taxa_inadimplencia_valor": "Taxa de inadimplência por valor",
        },
        color_discrete_sequence=["#b94e48", "#c08b2c", "#2f5d7c", "#2f7d5b"],
    )
    fig_metodo.update_layout(showlegend=False, yaxis_tickformat=".2%")
    st.plotly_chart(fig_metodo, use_container_width=True)

with tab_risco:
    componentes_score = pd.DataFrame(
        {
            "Componente": [
                "Quantidade de atrasos",
                "Frequência de inadimplência",
                "Dias médios de atraso",
                "Valor em aberto",
                "Método de pagamento",
            ],
            "Peso normalizado": [
                pesos_risco_normalizados["quantidade_atrasos"],
                pesos_risco_normalizados["frequencia_inadimplencia"],
                pesos_risco_normalizados["dias_medios_atraso"],
                pesos_risco_normalizados["valor_em_aberto"],
                pesos_risco_normalizados["metodo_pagamento"],
            ],
        }
    )
    componentes_score["Peso normalizado"] = componentes_score["Peso normalizado"].map(
        formatar_percentual
    )
    with st.expander("Auditoria do score de risco", expanded=False):
        st.dataframe(componentes_score, use_container_width=True, hide_index=True)
        st.caption(
            "Baixo risco: score abaixo de "
            f"{formatar_decimal(limites_risco.baixo_risco_max)} | "
            "Médio risco: score abaixo de "
            f"{formatar_decimal(limites_risco.medio_risco_max)} | "
            "Alto risco: score igual ou superior ao limite médio."
        )

    st.subheader("Distribuição do risco de inadimplência")
    dist_risco = (
        df_atual.groupby("segmento_risco")
        .agg(
            apolices=("id_apolice", "nunique"),
            valor_em_aberto=("valor_em_aberto", "sum"),
            score_medio=("score_inadimplencia", "mean"),
        )
        .reset_index()
    )
    ordem_risco = ["Baixo risco", "Medio risco", "Alto risco"]
    dist_risco["segmento_risco"] = pd.Categorical(
        dist_risco["segmento_risco"],
        categories=ordem_risco,
        ordered=True,
    )
    dist_risco = dist_risco.sort_values("segmento_risco")

    fig_risco = px.bar(
        dist_risco,
        x="segmento_risco",
        y="apolices",
        color="segmento_risco",
        labels={"segmento_risco": "Segmento", "apolices": "Apólices"},
        color_discrete_sequence=["#2f7d5b", "#c08b2c", "#b94e48"],
    )
    fig_risco.update_layout(showlegend=False)
    st.plotly_chart(fig_risco, use_container_width=True)

    fig_score = px.histogram(
        df_atual.drop_duplicates("id_apolice"),
        x="score_inadimplencia",
        color="segmento_risco",
        nbins=30,
        labels={
            "score_inadimplencia": "Score de inadimplência",
            "segmento_risco": "Segmento de risco",
        },
        color_discrete_sequence=["#2f7d5b", "#c08b2c", "#b94e48"],
    )
    st.plotly_chart(fig_score, use_container_width=True)

    st.subheader("Ranking atuarial de prioridade para migração")
    ranking_exibicao = ranking.head(15).copy()
    ranking_exibicao["recuperacao_potencial_pix"] = ranking_exibicao[
        "recuperacao_potencial_pix"
    ].map(formatar_moeda)
    ranking_exibicao["valor_em_aberto"] = ranking_exibicao["valor_em_aberto"].map(
        formatar_moeda
    )
    ranking_exibicao["score_medio"] = ranking_exibicao["score_medio"].map(formatar_decimal)
    st.dataframe(ranking_exibicao, use_container_width=True, hide_index=True)

with tab_base:
    st.subheader("Prévia da base analítica")
    st.dataframe(df_atual.head(50), use_container_width=True)

    st.subheader("Prévia da estimativa com Pix")
    st.dataframe(df_pix.head(50), use_container_width=True)

    csv_comparativo = comparativo.to_csv(index=False).encode("utf-8")
    csv_base_pix = df_pix.to_csv(index=False).encode("utf-8")

    col_down1, col_down2 = st.columns(2)
    with col_down1:
        st.download_button(
            label="Baixar comparação",
            data=csv_comparativo,
            file_name="comparativo_atuarial_pix.csv",
            mime="text/csv",
        )
    with col_down2:
        st.download_button(
            label="Baixar base estimada",
            data=csv_base_pix,
            file_name="base_estimada_pix.csv",
            mime="text/csv",
        )
