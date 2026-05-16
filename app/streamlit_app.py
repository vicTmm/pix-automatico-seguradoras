from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
import sys
import unicodedata

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
from src.data.loaders import carregar_arquivo_pagamentos
from src.data.schema import REQUIRED_PAYMENT_COLUMNS, preparar_base_pagamentos


st.set_page_config(
    page_title="Simulação Atuarial | Pix Automático",
    layout="wide",
    initial_sidebar_state="expanded",
)

px.defaults.template = "plotly_dark"

TAXA_RECUPERACAO_PIX_PADRAO = 0.40
TAXA_CANCELAMENTO_INADIMPLENTES_PADRAO = 0.25
TAXA_DESCONTO_ANUAL_PADRAO = 0.10
PESOS_RISCO_PADRAO = RiskScoreWeights()
LIMITES_RISCO_PADRAO = RiskSegmentationThresholds()
RECOMMENDED_PAYMENT_COLUMNS = [
    "id_pagamento",
    "id_segurado",
    "id_parcela",
    "competencia",
    "ramo",
    "perfil_pagamento",
    "valor_esperado",
]
CHART_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": [
        "zoomIn2d",
        "zoomOut2d",
        "lasso2d",
        "select2d",
        "autoScale2d",
    ],
}
PALETA = {
    "ink": "#E2E8F0",
    "muted": "#94A3B8",
    "line": "rgba(148, 163, 184, 0.16)",
    "brand": "#38BDF8",
    "brand_soft": "rgba(56, 189, 248, 0.18)",
    "teal": "#2DD4BF",
    "teal_soft": "rgba(45, 212, 191, 0.16)",
    "amber": "#F59E0B",
    "amber_soft": "rgba(245, 158, 11, 0.16)",
    "red": "#FB7185",
    "red_soft": "rgba(251, 113, 133, 0.16)",
    "navy": "#60A5FA",
    "surface": "#0F172A",
}
RISK_COLORS = {
    "Baixo risco": "#2DD4BF",
    "Médio risco": "#F59E0B",
    "Alto risco": "#FB7185",
}
ROTULOS_EXIBICAO = {
    "Cartao": "Cartão",
    "Debito": "Débito",
    "Pix Automatico": "Pix Automático",
    "Estimativa com Pix Automatico": "Estimativa com Pix Automático",
    "Medio risco": "Médio risco",
}


@dataclass(frozen=True)
class AnalysisResults:
    df_atual: pd.DataFrame
    df_pix: pd.DataFrame
    indicadores_atual: dict[str, float]
    indicadores_pix: dict[str, float]
    comparativo: pd.DataFrame
    fluxo: pd.DataFrame
    inad_metodo: pd.DataFrame
    ranking: pd.DataFrame
    diagnostico: list[dict[str, str]]


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


def formatar_decimal(valor: float) -> str:
    return f"{valor:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_dias_mercado(valor: float) -> str:
    dias = int(round(valor))
    unidade = "dia" if dias == 1 else "dias"
    return f"{dias} {unidade}"


def formatar_mes_competencia(valor: pd.Timestamp) -> str:
    return valor.strftime("%m/%Y")


def normalizar_texto(texto: str) -> str:
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texto.lower())
        if not unicodedata.combining(caractere)
    )


def padronizar_rotulos_exibicao(df: pd.DataFrame) -> pd.DataFrame:
    base = df.copy()
    for coluna in ["segmento_risco", "metodo_pagamento", "visao"]:
        if coluna in base.columns:
            base[coluna] = base[coluna].replace(ROTULOS_EXIBICAO)
    return base


def aplicar_estilo_figura(fig: go.Figure, titulo: str | None = None) -> go.Figure:
    layout_config = dict(
        paper_bgcolor="rgba(0, 0, 0, 0)",
        plot_bgcolor="rgba(0, 0, 0, 0)",
        font=dict(
            family="IBM Plex Sans, Source Sans Pro, Segoe UI, sans-serif",
            color=PALETA["ink"],
            size=13,
        ),
        margin=dict(l=12, r=12, t=56, b=12),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            title_text="",
        ),
        hoverlabel=dict(
            bgcolor=PALETA["surface"],
            bordercolor=PALETA["line"],
            font=dict(color=PALETA["ink"]),
        ),
    )
    if titulo is not None:
        layout_config["title"] = titulo

    fig.update_layout(**layout_config)
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        color=PALETA["muted"],
        title_font=dict(color=PALETA["ink"]),
    )
    fig.update_yaxes(
        gridcolor="rgba(148, 163, 184, 0.14)",
        zeroline=False,
        color=PALETA["muted"],
        title_font=dict(color=PALETA["ink"]),
    )
    return fig


def formatar_valor_indicador(indicador: str, valor: float) -> str:
    indicador_normalizado = normalizar_texto(indicador)

    if "inadimplencia" in indicador_normalizado or "persistencia" in indicador_normalizado:
        return formatar_percentual(valor)

    if "atraso" in indicador_normalizado:
        return formatar_dias_mercado(valor)

    if "cancelamentos" in indicador_normalizado:
        return formatar_numero(valor)

    return formatar_moeda(valor)


def montar_comparativo_formatado(comparativo: pd.DataFrame) -> pd.DataFrame:
    exibicao = comparativo.copy().rename(
        columns={
            "Carteira atual": "Carteira atual",
            "Estimativa com Pix Automatico": "Estimativa com Pix Automático",
            "Variacao": "Variação",
        }
    )

    nomes_indicadores = {
        "Premio esperado": "Prêmio esperado",
        "Premio recebido": "Prêmio recebido",
        "Premio inadimplente": "Prêmio em aberto",
        "Premio recuperado com Pix": "Prêmio recuperado com Pix",
        "Taxa de inadimplencia por quantidade": "Inadimplência por quantidade",
        "Taxa de inadimplencia por valor": "Inadimplência por valor",
        "Persistencia estimada": "Persistência estimada",
        "Cancelamentos estimados": "Cancelamentos estimados",
        "Atraso medio": "Atraso médio",
        "Valor presente dos recebimentos": "Valor presente",
    }
    exibicao["Indicador"] = exibicao["Indicador"].replace(nomes_indicadores)

    for coluna in ["Carteira atual", "Estimativa com Pix Automático", "Variação"]:
        exibicao[coluna] = exibicao.apply(
            lambda row: formatar_valor_indicador(row["Indicador"], row[coluna]),
            axis=1,
        )

    return exibicao


def compor_frente_prioridade(row: pd.Series) -> str:
    partes = []

    if "ramo" in row.index and pd.notna(row.get("ramo")):
        partes.append(str(row["ramo"]))

    partes.extend([str(row["segmento_risco"]), str(row["metodo_pagamento"])])
    return " | ".join(partes)


def gerar_diagnostico_executivo(
    indicadores_atual: dict[str, float],
    indicadores_pix: dict[str, float],
    inadimplencia_metodo: pd.DataFrame,
    ranking_prioridade: pd.DataFrame,
) -> list[dict[str, str]]:
    ganho_recebimento = (
        indicadores_pix["premio_recebido"] - indicadores_atual["premio_recebido"]
    )
    reducao_inad_valor = (
        indicadores_atual["taxa_inadimplencia_valor"]
        - indicadores_pix["taxa_inadimplencia_valor"]
    )
    ganho_persistencia = (
        indicadores_pix["persistencia_estimada"]
        - indicadores_atual["persistencia_estimada"]
    )
    ganho_vp = (
        indicadores_pix["valor_presente_recebimentos"]
        - indicadores_atual["valor_presente_recebimentos"]
    )

    diagnostico = [
        {
            "titulo": "Resultado da simulação",
            "descricao": (
                f"A simulação converte {formatar_moeda(ganho_recebimento)} de prêmio "
                "em aberto em recebimento, sem alterar o prêmio esperado da carteira."
            ),
            "classe": "positivo",
        },
        {
            "titulo": "Efeito sobre a inadimplência",
            "descricao": (
                f"A inadimplência por valor recua {formatar_percentual(reducao_inad_valor)} "
                f"e a persistência aumenta {formatar_percentual(ganho_persistencia)}."
            ),
            "classe": "positivo",
        },
        {
            "titulo": "Efeito econômico",
            "descricao": (
                "O valor presente dos recebimentos aumenta em "
                f"{formatar_moeda(ganho_vp)}, reforçando a qualidade do fluxo projetado."
            ),
            "classe": "neutro",
        },
    ]

    if not inadimplencia_metodo.empty:
        metodo_critico = inadimplencia_metodo.iloc[0]
        diagnostico.append(
            {
                "titulo": "Meio de cobrança mais sensível",
                "descricao": (
                    f"{metodo_critico['metodo_pagamento']} concentra a maior taxa de "
                    "inadimplência por valor e deve liderar a agenda de revisão operacional."
                ),
                "classe": "atencao",
            }
        )

    if not ranking_prioridade.empty:
        prioridade = ranking_prioridade.iloc[0]
        diagnostico.append(
            {
                "titulo": "Grupo prioritário",
                "descricao": (
                    f"{compor_frente_prioridade(prioridade)} apresenta recuperação potencial de "
                    f"{formatar_moeda(prioridade['recuperacao_potencial_pix'])}."
                ),
                "classe": "neutro",
            }
        )

    return diagnostico[:4]


def montar_template_importacao() -> bytes:
    exemplo = pd.DataFrame(
        {
            "id_apolice": ["AP-1001", "AP-1001", "AP-1002"],
            "data_vencimento": ["2025-01-10", "2025-02-10", "2025-01-15"],
            "data_pagamento": ["2025-01-10", "", "2025-01-18"],
            "valor_pago": [540.0, 0.0, 320.0],
            "status": ["Pago", "Inadimplente", "Pago"],
            "metodo_pagamento": ["Boleto", "Boleto", "Cartão"],
            "valor_esperado": [540.0, 540.0, 320.0],
            "ramo": ["Auto", "Auto", "Vida"],
        }
    )
    return exemplo.to_csv(index=False).encode("utf-8")


def montar_dicionario_colunas() -> pd.DataFrame:
    descricoes = {
        "id_apolice": ("Obrigatória", "Identificador único da apólice"),
        "data_vencimento": ("Obrigatória", "Data de vencimento da cobrança"),
        "data_pagamento": ("Obrigatória", "Data do pagamento ou campo vazio em caso de inadimplência"),
        "valor_pago": ("Obrigatória", "Valor efetivamente liquidado"),
        "status": ("Obrigatória", 'Utilize "Pago" ou "Inadimplente"'),
        "metodo_pagamento": ("Obrigatória", "Meio de cobrança utilizado"),
        "valor_esperado": ("Recomendada", "Prêmio originalmente esperado"),
        "ramo": ("Recomendada", "Linha de negócio ou ramo"),
        "competencia": ("Recomendada", "Competência contábil da parcela"),
        "id_parcela": ("Recomendada", "Identificador da parcela"),
        "id_pagamento": ("Recomendada", "Identificador da transação"),
        "id_segurado": ("Recomendada", "Identificador do segurado"),
        "perfil_pagamento": ("Recomendada", "Padrão de comportamento de pagamento"),
    }
    return pd.DataFrame(
        [
            {
                "Coluna": coluna,
                "Classificação": descricoes[coluna][0],
                "Descrição": descricoes[coluna][1],
            }
            for coluna in descricoes
        ]
    )


def render_card_metrica(
    label: str,
    valor: str,
    delta: str | None = None,
    classe_delta: str = "neutro",
):
    delta_html = ""
    if delta:
        delta_html = f'<div class="metric-delta {classe_delta}">{delta}</div>'

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


def render_card_insight(titulo: str, descricao: str, classe: str):
    st.markdown(
        f"""
        <div class="insight-card {classe}">
            <div class="insight-title">{titulo}</div>
            <div class="insight-body">{descricao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def injetar_estilos():
    st.markdown(
        """
        <style>
            :root {
                --bg: #08111f;
                --surface: rgba(15, 23, 42, 0.78);
                --surface-soft: rgba(15, 23, 42, 0.62);
                --surface-strong: rgba(8, 15, 28, 0.88);
                --ink: #e2e8f0;
                --muted: #94a3b8;
                --line: rgba(148, 163, 184, 0.16);
                --brand: #38bdf8;
                --brand-soft: rgba(56, 189, 248, 0.18);
                --teal: #2dd4bf;
                --teal-soft: rgba(45, 212, 191, 0.16);
                --amber: #f59e0b;
                --amber-soft: rgba(245, 158, 11, 0.16);
                --red: #fb7185;
                --red-soft: rgba(251, 113, 133, 0.16);
            }

            .stApp {
                background:
                    radial-gradient(circle at top right, rgba(56, 189, 248, 0.14), transparent 22%),
                    radial-gradient(circle at top left, rgba(45, 212, 191, 0.10), transparent 16%),
                    linear-gradient(180deg, #07101c 0%, #091423 48%, #08111f 100%);
                color: var(--ink);
            }

            .block-container {
                padding-top: 1.3rem;
                padding-bottom: 3rem;
                max-width: 1320px;
            }

            [data-testid="stSidebar"] {
                background:
                    radial-gradient(circle at top right, rgba(56, 189, 248, 0.12), transparent 22%),
                    radial-gradient(circle at top left, rgba(45, 212, 191, 0.10), transparent 18%),
                    linear-gradient(180deg, #0d1726 0%, #102336 48%, #0c1a2b 100%);
                border-right: 1px solid rgba(148, 163, 184, 0.16);
            }

            [data-testid="stSidebar"] .block-container {
                padding-top: 1.1rem;
            }

            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3,
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] .stCaption,
            [data-testid="stSidebar"] p {
                color: #dbe7f3;
            }

            [data-testid="stSidebar"] .stMarkdown,
            [data-testid="stSidebar"] .stCaption,
            [data-testid="stSidebar"] small,
            [data-testid="stSidebar"] span {
                color: #dbe7f3;
            }

            [data-testid="stSidebar"] hr {
                border-color: rgba(148, 163, 184, 0.12);
            }

            .sidebar-brand-card {
                position: relative;
                overflow: hidden;
                margin-bottom: 1rem;
                padding: 1rem 1rem 0.95rem;
                border-radius: 22px;
                border: 1px solid rgba(148, 163, 184, 0.14);
                background:
                    linear-gradient(155deg, rgba(15, 94, 132, 0.26), rgba(15, 118, 110, 0.18)),
                    rgba(15, 23, 42, 0.55);
                box-shadow: 0 18px 40px rgba(2, 8, 23, 0.28);
            }

            .sidebar-brand-card::after {
                content: "";
                position: absolute;
                right: -36px;
                top: -44px;
                width: 130px;
                height: 130px;
                border-radius: 999px;
                background: radial-gradient(circle, rgba(125, 211, 252, 0.24), transparent 68%);
            }

            .sidebar-kicker {
                color: rgba(226, 232, 240, 0.72);
                font-size: 0.72rem;
                font-weight: 760;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 0.35rem;
            }

            .sidebar-title {
                color: #f8fbff;
                font-size: 1.18rem;
                line-height: 1.15;
                font-weight: 760;
                margin-bottom: 0.4rem;
                max-width: 220px;
            }

            .sidebar-copy {
                color: rgba(226, 232, 240, 0.82);
                font-size: 0.85rem;
                line-height: 1.55;
            }

            .sidebar-section-label {
                color: rgba(226, 232, 240, 0.76);
                font-size: 0.74rem;
                font-weight: 760;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin: 0.1rem 0 0.55rem;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploader"],
            [data-testid="stSidebar"] [data-testid="stExpander"],
            [data-testid="stSidebar"] .stDateInput > div > div,
            [data-testid="stSidebar"] .stMultiSelect > div > div,
            [data-testid="stSidebar"] .stSelectbox > div > div,
            [data-testid="stSidebar"] div[data-baseweb="select"] > div {
                background: linear-gradient(
                    180deg,
                    rgba(15, 23, 42, 0.42),
                    rgba(15, 23, 42, 0.58)
                );
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 18px;
                box-shadow: 0 12px 30px rgba(2, 8, 23, 0.18);
                backdrop-filter: blur(12px);
            }

            [data-testid="stSidebar"] [data-testid="stFileUploader"] {
                padding: 10px;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
                background: linear-gradient(
                    180deg,
                    rgba(15, 23, 42, 0.18),
                    rgba(15, 23, 42, 0.30)
                );
                border: 1px dashed rgba(125, 211, 252, 0.28);
                border-radius: 14px;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] * {
                color: rgba(226, 232, 240, 0.72);
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button,
            [data-testid="stSidebar"] .stDownloadButton button,
            [data-testid="stSidebar"] .stButton button {
                min-height: 42px;
                border-radius: 12px;
                border: 1px solid rgba(125, 211, 252, 0.16);
                background: linear-gradient(
                    180deg,
                    rgba(15, 94, 132, 0.92),
                    rgba(12, 74, 110, 0.98)
                );
                color: #f8fbff;
                font-weight: 680;
                box-shadow: 0 10px 22px rgba(2, 8, 23, 0.24);
                transition: all 160ms ease;
            }

            [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button:hover,
            [data-testid="stSidebar"] .stDownloadButton button:hover,
            [data-testid="stSidebar"] .stButton button:hover {
                border-color: rgba(125, 211, 252, 0.28);
                background: linear-gradient(
                    180deg,
                    rgba(17, 119, 163, 1),
                    rgba(15, 94, 132, 1)
                );
                color: #ffffff;
                box-shadow: 0 14px 26px rgba(2, 8, 23, 0.28);
            }

            [data-testid="stSidebar"] [data-testid="stExpander"] details {
                background: transparent;
            }

            [data-testid="stSidebar"] [data-testid="stExpander"] summary {
                border-radius: 18px;
                color: #f8fbff;
            }

            [data-testid="stSidebar"] [data-testid="stExpanderDetails"] {
                padding-top: 0.2rem;
            }

            [data-testid="stSidebar"] .stDateInput input,
            [data-testid="stSidebar"] .stMultiSelect input,
            [data-testid="stSidebar"] .stSelectbox input,
            [data-testid="stSidebar"] div[data-baseweb="select"] *,
            [data-testid="stSidebar"] .stDateInput svg,
            [data-testid="stSidebar"] .stMultiSelect svg,
            [data-testid="stSidebar"] .stSelectbox svg {
                color: #f8fbff;
                fill: #f8fbff;
            }

            [data-testid="stSidebar"] div[data-baseweb="tag"] {
                border-radius: 999px;
                background: rgba(125, 211, 252, 0.14);
                border: 1px solid rgba(125, 211, 252, 0.16);
            }

            [data-testid="stSidebar"] div[data-baseweb="tag"] span {
                color: #e0f2fe;
            }

            [data-testid="stSidebar"] .stDataFrame {
                background: rgba(255, 255, 255, 0.03);
                border-radius: 14px;
            }

            [data-testid="stAppViewContainer"] .main {
                background: transparent;
            }

            [data-testid="stAppViewContainer"] .main .block-container {
                position: relative;
            }

            [data-testid="stAppViewContainer"] .main p,
            [data-testid="stAppViewContainer"] .main label,
            [data-testid="stAppViewContainer"] .main .stCaption,
            [data-testid="stAppViewContainer"] .main small {
                color: var(--ink);
            }

            [data-testid="stAppViewContainer"] .main .stCaption,
            [data-testid="stAppViewContainer"] .main .caption {
                color: rgba(148, 163, 184, 0.9);
            }

            [data-testid="stAppViewContainer"] .main [data-testid="stPlotlyChart"],
            [data-testid="stAppViewContainer"] .main [data-testid="stDataFrame"],
            [data-testid="stAppViewContainer"] .main .stDownloadButton,
            [data-testid="stAppViewContainer"] .main [data-testid="stExpander"] {
                border: 1px solid var(--line);
                border-radius: 22px;
                background:
                    linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(8, 15, 28, 0.82));
                box-shadow: 0 22px 48px rgba(2, 8, 23, 0.22);
                backdrop-filter: blur(12px);
            }

            [data-testid="stAppViewContainer"] .main [data-testid="stPlotlyChart"],
            [data-testid="stAppViewContainer"] .main [data-testid="stDataFrame"] {
                padding: 10px 12px;
            }

            [data-testid="stAppViewContainer"] .main [data-testid="stExpander"] {
                padding: 2px 10px;
            }

            [data-testid="stAppViewContainer"] .main [data-testid="stExpander"] details {
                background: transparent;
            }

            [data-testid="stAppViewContainer"] .main [data-testid="stExpander"] summary,
            [data-testid="stAppViewContainer"] .main [data-testid="stExpander"] label {
                color: var(--ink);
            }

            [data-testid="stAppViewContainer"] .main .stDownloadButton {
                padding: 10px;
            }

            [data-testid="stAppViewContainer"] .main .stDownloadButton button,
            [data-testid="stAppViewContainer"] .main .stButton button {
                min-height: 42px;
                width: 100%;
                border-radius: 12px;
                border: 1px solid rgba(56, 189, 248, 0.18);
                background: linear-gradient(
                    180deg,
                    rgba(15, 94, 132, 0.92),
                    rgba(12, 74, 110, 0.98)
                );
                color: #f8fbff;
                font-weight: 680;
                box-shadow: 0 12px 24px rgba(2, 8, 23, 0.20);
                transition: all 160ms ease;
            }

            [data-testid="stAppViewContainer"] .main .stDownloadButton button:hover,
            [data-testid="stAppViewContainer"] .main .stButton button:hover {
                border-color: rgba(125, 211, 252, 0.28);
                background: linear-gradient(
                    180deg,
                    rgba(17, 119, 163, 1),
                    rgba(15, 94, 132, 1)
                );
                color: #ffffff;
                box-shadow: 0 16px 28px rgba(2, 8, 23, 0.24);
            }

            .hero-panel {
                position: relative;
                overflow: hidden;
                border: 1px solid var(--line);
                border-radius: 24px;
                padding: 28px 30px;
                margin-bottom: 18px;
                background:
                    linear-gradient(135deg, rgba(15, 94, 132, 0.22), rgba(15, 118, 110, 0.14)),
                    linear-gradient(180deg, rgba(15, 23, 42, 0.84), rgba(8, 15, 28, 0.92));
                box-shadow: 0 28px 56px rgba(2, 8, 23, 0.26);
                backdrop-filter: blur(12px);
            }

            .hero-panel::after {
                content: "";
                position: absolute;
                inset: auto -40px -60px auto;
                width: 220px;
                height: 220px;
                border-radius: 999px;
                background: radial-gradient(circle, rgba(56, 189, 248, 0.18), transparent 70%);
            }

            .eyebrow {
                color: var(--brand);
                font-size: 0.78rem;
                font-weight: 760;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                margin-bottom: 10px;
            }

            .hero-title {
                color: #f8fbff;
                font-size: 2.25rem;
                line-height: 1.05;
                font-weight: 760;
                margin-bottom: 10px;
                max-width: 880px;
            }

            .hero-subtitle {
                color: rgba(226, 232, 240, 0.82);
                font-size: 1rem;
                line-height: 1.6;
                max-width: 920px;
                margin-bottom: 18px;
            }

            .tag-row {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            .hero-tag {
                border: 1px solid rgba(148, 163, 184, 0.14);
                border-radius: 999px;
                padding: 6px 12px;
                background: rgba(15, 23, 42, 0.42);
                color: rgba(226, 232, 240, 0.92);
                font-size: 0.82rem;
                font-weight: 650;
            }

            .metric-card,
            .insight-card,
            .empty-card {
                border: 1px solid var(--line);
                border-radius: 22px;
                background:
                    linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(8, 15, 28, 0.82));
                box-shadow: 0 20px 42px rgba(2, 8, 23, 0.22);
                backdrop-filter: blur(12px);
            }

            .metric-card {
                min-height: 136px;
                padding: 18px 18px 16px;
                transition: transform 160ms ease, box-shadow 160ms ease;
            }

            .metric-card:hover,
            .insight-card:hover,
            .empty-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 24px 44px rgba(2, 8, 23, 0.28);
            }

            .metric-label {
                color: rgba(148, 163, 184, 0.9);
                font-size: 0.82rem;
                font-weight: 650;
                line-height: 1.35;
                margin-bottom: 10px;
            }

            .metric-value {
                color: #f8fbff;
                font-size: 1.82rem;
                line-height: 1.08;
                font-weight: 760;
            }

            .metric-delta {
                display: inline-flex;
                align-items: center;
                margin-top: 12px;
                padding: 4px 10px;
                border-radius: 999px;
                font-size: 0.82rem;
                font-weight: 700;
            }

            .metric-delta.positivo {
                color: var(--teal);
                background: var(--teal-soft);
            }

            .metric-delta.atencao {
                color: var(--amber);
                background: var(--amber-soft);
            }

            .metric-delta.neutro {
                color: var(--brand);
                background: var(--brand-soft);
            }

            .insight-card {
                min-height: 178px;
                padding: 18px 18px 16px;
                border-left: 4px solid rgba(56, 189, 248, 0.55);
            }

            .insight-card.positivo {
                border-left-color: rgba(45, 212, 191, 0.72);
            }

            .insight-card.atencao {
                border-left-color: rgba(245, 158, 11, 0.72);
            }

            .insight-card.neutro {
                border-left-color: rgba(56, 189, 248, 0.62);
            }

            .insight-title {
                color: #f8fbff;
                font-size: 0.92rem;
                font-weight: 760;
                margin-bottom: 8px;
            }

            .insight-body {
                color: rgba(226, 232, 240, 0.82);
                font-size: 0.94rem;
                line-height: 1.58;
            }

            .section-heading {
                margin: 8px 0 12px;
            }

            .diagnostic-spacer {
                height: 26px;
            }

            .chart-block-title {
                color: #f8fbff;
                font-size: 1.02rem;
                font-weight: 760;
                line-height: 1.2;
                margin: 2px 0 10px 4px;
            }

            .section-title {
                color: #f8fbff;
                font-size: 1.16rem;
                font-weight: 760;
                margin-bottom: 4px;
            }

            .section-copy {
                color: rgba(148, 163, 184, 0.92);
                font-size: 0.92rem;
                line-height: 1.55;
            }

            .status-banner {
                border: 1px solid var(--line);
                border-radius: 18px;
                padding: 14px 16px;
                background:
                    linear-gradient(180deg, rgba(15, 23, 42, 0.76), rgba(8, 15, 28, 0.84));
                margin-bottom: 16px;
                box-shadow: 0 18px 34px rgba(2, 8, 23, 0.18);
            }

            .status-banner.warning {
                border-left: 4px solid rgba(245, 158, 11, 0.62);
            }

            .status-banner.info {
                border-left: 4px solid rgba(56, 189, 248, 0.62);
            }

            .status-title {
                color: #f8fbff;
                font-size: 0.9rem;
                font-weight: 750;
                margin-bottom: 4px;
            }

            .status-text {
                color: rgba(226, 232, 240, 0.84);
                font-size: 0.9rem;
                line-height: 1.5;
            }

            .empty-card {
                padding: 22px 22px 20px;
                min-height: 184px;
            }

            .empty-title {
                color: #f8fbff;
                font-size: 1rem;
                font-weight: 760;
                margin-bottom: 8px;
            }

            .empty-body {
                color: rgba(226, 232, 240, 0.82);
                font-size: 0.92rem;
                line-height: 1.6;
            }

            .stTabs [data-baseweb="tab-list"] {
                gap: 0.7rem;
                margin-bottom: 0.8rem;
            }

            .stTabs [data-baseweb="tab"] {
                height: 44px;
                border-radius: 999px;
                padding: 0 18px;
                border: 1px solid rgba(148, 163, 184, 0.14);
                background: rgba(15, 23, 42, 0.52);
                color: rgba(226, 232, 240, 0.82);
            }

            .stTabs [aria-selected="true"] {
                background: linear-gradient(
                    180deg,
                    rgba(15, 94, 132, 0.92),
                    rgba(12, 74, 110, 0.98)
                );
                color: #ffffff;
                border-color: rgba(125, 211, 252, 0.28);
                box-shadow: 0 12px 24px rgba(2, 8, 23, 0.18);
            }

            [data-testid="stFileUploader"] {
                background: rgba(255, 255, 255, 0.75);
                border-radius: 18px;
                padding: 4px;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_titulo_secao(titulo: str, descricao: str):
    st.markdown(
        f"""
        <div class="section-heading">
            <div class="section-title">{titulo}</div>
            <div class="section-copy">{descricao}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_titulo_grafico(titulo: str):
    st.markdown(
        f'<div class="chart-block-title">{titulo}</div>',
        unsafe_allow_html=True,
    )


def render_banner_status(titulo: str, texto: str, variante: str):
    st.markdown(
        f"""
        <div class="status-banner {variante}">
            <div class="status-title">{titulo}</div>
            <div class="status-text">{texto}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(nome_arquivo: str | None, df: pd.DataFrame | None):
    if df is None or df.empty:
        tags = [
            "Trabalho de Conclusão de Curso",
            "Ciências Atuariais",
            "Seguradoras brasileiras",
            "Simulação aplicada à inadimplência e ao fluxo de caixa",
        ]
        subtitulo = (
            "Proposta de ferramenta de simulação atuarial para mensuração dos impactos "
            "do Pix Automático sobre a inadimplência, a persistência e o fluxo de caixa "
            "de seguradoras brasileiras."
        )
    else:
        inicio = df["data_vencimento"].min()
        fim = df["data_vencimento"].max()
        tags = [
            f"Arquivo: {nome_arquivo}",
            f"Apólices: {formatar_numero(df['id_apolice'].nunique())}",
            f"Cobranças: {formatar_numero(len(df))}",
            f"Período: {formatar_mes_competencia(inicio)} a {formatar_mes_competencia(fim)}",
        ]
        subtitulo = (
            "Aplicação da proposta metodológica do estudo à carteira observada, com "
            "estimativas sobre inadimplência, recuperação de prêmio e comportamento "
            "do fluxo de caixa sob adoção do Pix Automático."
        )

    tags_html = "".join(f'<span class="hero-tag">{tag}</span>' for tag in tags)
    st.markdown(
        f"""
        <section class="hero-panel">
            <div class="eyebrow">Trabalho de Conclusão de Curso | Ciências Atuariais</div>
            <div class="hero-title">Ferramenta de simulação atuarial para avaliação do Pix Automático</div>
            <div class="hero-subtitle">{subtitulo}</div>
            <div class="tag-row">{tags_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_estado_vazio():
    render_titulo_secao(
        "Proposta de ferramenta para o estudo atuarial",
        "A aplicação foi estruturada para apoiar a defesa do projeto, permitindo importar a base observada, aplicar a simulação e apresentar evidências quantitativas sobre os efeitos do Pix Automático.",
    )

    colunas = st.columns(3)
    cards = [
        (
            "Problema investigado",
            "Mensurar de forma estruturada os impactos do Pix Automático sobre a inadimplência e o fluxo de caixa de seguradoras brasileiras.",
        ),
        (
            "Contribuição da ferramenta",
            "Transformar a base de pagamentos em uma simulação atuarial com indicadores comparativos, leitura técnica e apoio à interpretação dos resultados.",
        ),
        (
            "Base empírica do estudo",
            "Utilizar dados observados da carteira para reproduzir cenários e sustentar a análise da proposta com evidências quantitativas.",
        ),
    ]

    for coluna, (titulo, corpo) in zip(colunas, cards):
        with coluna:
            st.markdown(
                f"""
                <div class="empty-card">
                    <div class="empty-title">{titulo}</div>
                    <div class="empty-body">{corpo}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

def render_sidebar_upload(
    template_bytes: bytes,
) -> st.runtime.uploaded_file_manager.UploadedFile | None:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand-card">
                <div class="sidebar-kicker">Projeto de TCC</div>
                <div class="sidebar-title">Ferramenta de simulação atuarial</div>
                <div class="sidebar-copy">
                    Carregue a base de pagamentos para aplicar a proposta metodológica
                    e observar os impactos estimados do Pix Automático sobre a carteira.
                </div>
            </div>
            <div class="sidebar-section-label">Base do estudo</div>
            """,
            unsafe_allow_html=True,
        )
        uploaded_file = st.file_uploader(
            "Base de pagamentos da seguradora",
            type=["csv", "xlsx", "xls"],
            help="Envie a base oficial da carteira para processamento atuarial.",
        )
        st.caption(
            "Formatos aceitos: CSV, XLSX e XLS. A base importada constitui o insumo empírico da simulação."
        )
        st.download_button(
            label="Modelo de importação",
            data=template_bytes,
            file_name="template_carteira_pix_automatico.csv",
            mime="text/csv",
            use_container_width=True,
        )
    return uploaded_file


def render_sidebar_filtros(df_segmentado: pd.DataFrame) -> dict[str, object]:
    filtros: dict[str, object] = {
        "metodos": [],
        "segmentos": [],
        "ramos": [],
        "periodo": None,
    }

    with st.sidebar:
        st.divider()
        st.markdown(
            '<div class="sidebar-section-label">Recorte da análise</div>',
            unsafe_allow_html=True,
        )

        inicio_padrao = df_segmentado["data_vencimento"].min().date()
        fim_padrao = df_segmentado["data_vencimento"].max().date()
        periodo = st.date_input(
            "Período de vencimento",
            value=(inicio_padrao, fim_padrao),
            min_value=inicio_padrao,
            max_value=fim_padrao,
        )

        metodos = sorted(
            df_segmentado["metodo_pagamento"].dropna().astype(str).unique().tolist()
        )
        segmentos = [
            item
            for item in ["Baixo risco", "Médio risco", "Alto risco"]
            if item in df_segmentado["segmento_risco"].dropna().astype(str).unique()
        ]

        filtros["metodos"] = st.multiselect(
            "Meios de cobrança",
            metodos,
            default=metodos,
        )
        filtros["segmentos"] = st.multiselect(
            "Faixas de risco",
            segmentos,
            default=segmentos,
        )

        if "ramo" in df_segmentado.columns:
            ramos = sorted(df_segmentado["ramo"].dropna().astype(str).unique().tolist())
            filtros["ramos"] = st.multiselect(
                "Ramos",
                ramos,
                default=ramos,
            )

        filtros["periodo"] = periodo

        with st.expander("Premissas do modelo", expanded=False):
            st.markdown(
                f"""
                - Recuperação de inadimplência com Pix: {formatar_percentual(TAXA_RECUPERACAO_PIX_PADRAO)}
                - Taxa de cancelamento sobre inadimplentes: {formatar_percentual(TAXA_CANCELAMENTO_INADIMPLENTES_PADRAO)}
                - Taxa de desconto anual: {formatar_percentual(TAXA_DESCONTO_ANUAL_PADRAO)}
                - Classificação de risco: índice padronizado de 0 a 100 por apólice
                """
            )

    return filtros


def normalizar_periodo(periodo, inicio_padrao, fim_padrao):
    if isinstance(periodo, tuple) and len(periodo) == 2:
        return periodo[0], periodo[1]
    return inicio_padrao, fim_padrao


def aplicar_filtros(df: pd.DataFrame, filtros: dict[str, object]) -> pd.DataFrame:
    filtrado = df.copy()

    if filtrado.empty:
        return filtrado

    inicio_padrao = filtrado["data_vencimento"].min().date()
    fim_padrao = filtrado["data_vencimento"].max().date()
    periodo = filtros.get("periodo")
    inicio, fim = normalizar_periodo(periodo, inicio_padrao, fim_padrao)
    mascara = filtrado["data_vencimento"].dt.date.between(inicio, fim)

    metodos = filtros.get("metodos") or []
    if metodos:
        mascara &= filtrado["metodo_pagamento"].isin(metodos)

    segmentos = filtros.get("segmentos") or []
    if segmentos:
        mascara &= filtrado["segmento_risco"].isin(segmentos)

    ramos = filtros.get("ramos") or []
    if ramos and "ramo" in filtrado.columns:
        mascara &= filtrado["ramo"].astype(str).isin(ramos)

    return filtrado.loc[mascara].copy()


@st.cache_data(show_spinner=False)
def carregar_base_upload(file_name: str, file_bytes: bytes) -> pd.DataFrame:
    buffer = io.BytesIO(file_bytes)
    buffer.name = file_name
    return carregar_arquivo_pagamentos(buffer)


def executar_analise(df_atual: pd.DataFrame) -> AnalysisResults:
    df_pix = simular_pix_automatico(df_atual, TAXA_RECUPERACAO_PIX_PADRAO)
    df_pix = aplicar_segmentacao_risco(
        df_pix,
        pesos=PESOS_RISCO_PADRAO,
        limites=LIMITES_RISCO_PADRAO,
    )
    df_pix = padronizar_rotulos_exibicao(df_pix)

    indicadores_atual = calcular_indicadores_atuariais(
        df_atual,
        TAXA_CANCELAMENTO_INADIMPLENTES_PADRAO,
        TAXA_DESCONTO_ANUAL_PADRAO,
    )
    indicadores_pix = calcular_indicadores_atuariais(
        df_pix,
        TAXA_CANCELAMENTO_INADIMPLENTES_PADRAO,
        TAXA_DESCONTO_ANUAL_PADRAO,
    )

    comparativo = montar_comparativo_indicadores(indicadores_atual, indicadores_pix)
    fluxo = montar_fluxo_caixa_mensal(df_atual, df_pix)
    fluxo = padronizar_rotulos_exibicao(fluxo)
    inad_metodo = inadimplencia_por_metodo(df_atual)
    inad_metodo = padronizar_rotulos_exibicao(inad_metodo)
    ranking = ranking_prioridade_migracao_pix(df_atual, TAXA_RECUPERACAO_PIX_PADRAO)
    ranking = padronizar_rotulos_exibicao(ranking)
    diagnostico = gerar_diagnostico_executivo(
        indicadores_atual,
        indicadores_pix,
        inad_metodo,
        ranking,
    )

    return AnalysisResults(
        df_atual=df_atual,
        df_pix=df_pix,
        indicadores_atual=indicadores_atual,
        indicadores_pix=indicadores_pix,
        comparativo=comparativo,
        fluxo=fluxo,
        inad_metodo=inad_metodo,
        ranking=ranking,
        diagnostico=diagnostico,
    )


def criar_figura_ponte_premio(
    indicadores_atual: dict[str, float],
    indicadores_pix: dict[str, float],
) -> go.Figure:
    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "total"],
            x=[
                "Prêmio esperado",
                "Diferença por inadimplência",
                "Recuperação com Pix",
                "Recebimento estimado",
            ],
            y=[
                indicadores_atual["premio_esperado"],
                -indicadores_atual["premio_inadimplente"],
                indicadores_pix["premio_recuperado_pix"],
                0,
            ],
            text=[
                formatar_moeda(indicadores_atual["premio_esperado"]),
                formatar_moeda(-indicadores_atual["premio_inadimplente"]),
                formatar_moeda(indicadores_pix["premio_recuperado_pix"]),
                formatar_moeda(indicadores_pix["premio_recebido"]),
            ],
            textposition="outside",
            connector={"line": {"color": "rgba(71, 85, 105, 0.35)", "width": 1.2}},
            increasing={"marker": {"color": PALETA["teal"]}},
            decreasing={"marker": {"color": PALETA["red"]}},
            totals={"marker": {"color": PALETA["brand"]}},
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        )
    )
    fig.update_yaxes(title="Valor (R$)")
    return aplicar_estilo_figura(fig, "Composição econômica do prêmio")


def criar_figura_fluxo(fluxo: pd.DataFrame) -> go.Figure:
    dados = fluxo.copy()
    dados["mes_dt"] = pd.to_datetime(dados["mes"])
    dados = dados.sort_values(["mes_dt", "visao"])

    atual = dados[dados["visao"] == "Atual"].copy()
    pix = dados[dados["visao"] == "Estimativa com Pix Automático"].copy()
    atual["recebido_label"] = atual["premio_recebido"].map(formatar_moeda)
    pix["recebido_label"] = pix["premio_recebido"].map(formatar_moeda)
    pix["recuperado_label"] = pix["premio_recuperado_pix"].map(formatar_moeda)

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=atual["mes_dt"],
            y=atual["premio_recebido"],
            mode="lines+markers",
            name="Recebimento atual",
            line=dict(color=PALETA["navy"], width=3),
            marker=dict(size=7),
            customdata=atual["recebido_label"],
            hovertemplate="%{x|%m/%Y}<br>Recebimento atual: %{customdata}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=pix["mes_dt"],
            y=pix["premio_recebido"],
            mode="lines+markers",
            name="Recebimento com Pix",
            line=dict(color=PALETA["teal"], width=3),
            marker=dict(size=7),
            customdata=pix["recebido_label"],
            hovertemplate="%{x|%m/%Y}<br>Recebimento com Pix: %{customdata}<extra></extra>",
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Bar(
            x=pix["mes_dt"],
            y=pix["premio_recuperado_pix"],
            name="Recuperação com Pix",
            marker_color=PALETA["amber"],
            opacity=0.28,
            customdata=pix["recuperado_label"],
            hovertemplate="%{x|%m/%Y}<br>Recuperação com Pix: %{customdata}<extra></extra>",
        ),
        secondary_y=True,
    )

    fig.update_yaxes(title_text="Prêmio recebido", secondary_y=False)
    fig.update_yaxes(title_text="Recuperação com Pix", secondary_y=True, showgrid=False)
    fig.update_layout(hovermode="x unified", bargap=0.22)
    return aplicar_estilo_figura(fig)


def criar_figura_inadimplencia_metodo(inad_metodo: pd.DataFrame) -> go.Figure:
    dados = inad_metodo.copy()
    dados["taxa_label"] = dados["taxa_inadimplencia_valor"].map(formatar_percentual_compacto)
    maior_taxa = float(dados["taxa_inadimplencia_valor"].max()) if not dados.empty else 0.0
    limite_superior = maior_taxa * 1.18 if maior_taxa > 0 else 1.0

    fig = px.bar(
        dados,
        x="taxa_inadimplencia_valor",
        y="metodo_pagamento",
        orientation="h",
        color="metodo_pagamento",
        text="taxa_label",
        color_discrete_sequence=[
            PALETA["red"],
            PALETA["amber"],
            PALETA["brand"],
            PALETA["teal"],
        ],
        labels={
            "metodo_pagamento": "Meio de cobrança",
            "taxa_inadimplencia_valor": "Inadimplência por valor",
        },
    )
    fig.update_layout(showlegend=False, margin=dict(l=12, r=44, t=56, b=12))
    fig.update_traces(
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}<br>%{text}<extra></extra>",
    )
    fig.update_xaxes(tickformat=".0%", range=[0, limite_superior])
    return aplicar_estilo_figura(fig, "Inadimplência por meio de cobrança")


def criar_figura_risco(df_atual: pd.DataFrame) -> go.Figure:
    dist_risco = (
        df_atual.groupby("segmento_risco")
        .agg(
            apolices=("id_apolice", "nunique"),
            valor_em_aberto=("valor_em_aberto", "sum"),
        )
        .reset_index()
    )

    ordem = [item for item in ["Baixo risco", "Médio risco", "Alto risco"] if item in dist_risco["segmento_risco"].tolist()]
    dist_risco["segmento_risco"] = pd.Categorical(
        dist_risco["segmento_risco"],
        categories=ordem,
        ordered=True,
    )
    dist_risco = dist_risco.sort_values("segmento_risco")
    base_pie = "valor_em_aberto" if dist_risco["valor_em_aberto"].sum() > 0 else "apolices"
    dist_risco["valor_label"] = dist_risco["valor_em_aberto"].map(formatar_moeda)
    dist_risco["apolices_label"] = dist_risco["apolices"].map(formatar_numero)

    fig = px.pie(
        dist_risco,
        values=base_pie,
        names="segmento_risco",
        hole=0.62,
        color="segmento_risco",
        color_discrete_map=RISK_COLORS,
    )
    fig.update_traces(
        textposition="inside",
        texttemplate="%{label}<br>%{percent}",
        customdata=dist_risco[["valor_label", "apolices_label"]],
        hovertemplate=(
            "%{label}<br>Valor em aberto: %{customdata[0]}"
            "<br>Apólices: %{customdata[1]}<extra></extra>"
        ),
    )
    return aplicar_estilo_figura(fig)


def criar_figura_score(df_atual: pd.DataFrame) -> go.Figure:
    score = df_atual.drop_duplicates("id_apolice").copy()
    fig = px.box(
        score,
        x="segmento_risco",
        y="score_inadimplencia",
        color="segmento_risco",
        color_discrete_map=RISK_COLORS,
        labels={
            "segmento_risco": "Segmento de risco",
            "score_inadimplencia": "Índice de inadimplência",
        },
        points="outliers",
    )
    fig.update_layout(showlegend=False)
    fig.update_yaxes(range=[0, 100])
    return aplicar_estilo_figura(fig)


def criar_figura_ranking(ranking: pd.DataFrame) -> go.Figure:
    dados = ranking.head(20).copy()
    dados["frente"] = dados.apply(compor_frente_prioridade, axis=1)
    dados["recuperacao_label"] = dados["recuperacao_potencial_pix"].map(formatar_moeda)
    dados["valor_aberto_label"] = dados["valor_em_aberto"].map(formatar_moeda)
    dados["score_label"] = dados["score_medio"].map(formatar_decimal)
    dados["apolices_label"] = dados["apolices"].map(formatar_numero)
    dados["cobrancas_label"] = dados["cobrancas"].map(formatar_numero)

    fig = px.scatter(
        dados,
        x="score_medio",
        y="recuperacao_potencial_pix",
        size="apolices",
        color="segmento_risco",
        color_discrete_map=RISK_COLORS,
        hover_name="frente",
        hover_data={
            "score_label": True,
            "recuperacao_label": True,
            "valor_aberto_label": True,
            "apolices_label": True,
            "cobrancas_label": True,
            "score_medio": False,
            "recuperacao_potencial_pix": False,
            "valor_em_aberto": False,
            "apolices": False,
            "cobrancas": False,
            "segmento_risco": False,
        },
        labels={
            "score_medio": "Índice médio de risco",
            "recuperacao_potencial_pix": "Recuperação potencial com Pix",
            "apolices": "Apólices",
            "score_label": "Índice médio de risco",
            "recuperacao_label": "Recuperação potencial com Pix",
            "valor_aberto_label": "Valor em aberto",
            "apolices_label": "Apólices",
            "cobrancas_label": "Cobranças",
        },
    )
    fig.update_traces(
        marker=dict(opacity=0.72, line=dict(width=1, color="rgba(255,255,255,0.75)"))
    )
    return aplicar_estilo_figura(fig)


def construir_metricas(resultados: AnalysisResults) -> list[dict[str, str]]:
    indicadores_atual = resultados.indicadores_atual
    indicadores_pix = resultados.indicadores_pix
    reducao_inad_valor = (
        indicadores_atual["taxa_inadimplencia_valor"]
        - indicadores_pix["taxa_inadimplencia_valor"]
    )
    ganho_recebido = indicadores_pix["premio_recebido"] - indicadores_atual["premio_recebido"]
    ganho_vp = (
        indicadores_pix["valor_presente_recebimentos"]
        - indicadores_atual["valor_presente_recebimentos"]
    )
    cancelamentos_evitados = (
        indicadores_atual["cancelamentos_estimados"]
        - indicadores_pix["cancelamentos_estimados"]
    )

    return [
        {
            "label": "Prêmio esperado",
            "valor": formatar_moeda_compacta(indicadores_atual["premio_esperado"]),
            "delta": None,
            "classe": "neutro",
        },
        {
            "label": "Prêmio em aberto",
            "valor": formatar_moeda_compacta(indicadores_atual["premio_inadimplente"]),
            "delta": formatar_percentual_compacto(indicadores_atual["taxa_inadimplencia_valor"]),
            "classe": "atencao",
        },
        {
            "label": "Recuperação potencial com Pix",
            "valor": formatar_moeda_compacta(indicadores_pix["premio_recuperado_pix"]),
            "delta": "Prêmio recuperado",
            "classe": "positivo",
        },
        {
            "label": "Recebimento com Pix",
            "valor": formatar_moeda_compacta(indicadores_pix["premio_recebido"]),
            "delta": f"+ {formatar_moeda_compacta(ganho_recebido)}",
            "classe": "positivo",
        },
        {
            "label": "Inadimplência por valor",
            "valor": formatar_percentual_compacto(indicadores_pix["taxa_inadimplencia_valor"]),
            "delta": f"- {formatar_percentual_compacto(reducao_inad_valor)}",
            "classe": "positivo",
        },
        {
            "label": "Persistência estimada",
            "valor": formatar_percentual_compacto(indicadores_pix["persistencia_estimada"]),
            "delta": "Menor pressão de cancelamento",
            "classe": "positivo",
        },
        {
            "label": "Valor presente dos recebimentos",
            "valor": formatar_moeda_compacta(indicadores_pix["valor_presente_recebimentos"]),
            "delta": f"+ {formatar_moeda_compacta(ganho_vp)}",
            "classe": "neutro",
        },
        {
            "label": "Cancelamentos evitados",
            "valor": formatar_numero(cancelamentos_evitados),
            "delta": "Estimativa atuarial",
            "classe": "neutro",
        },
    ]


def render_metricas(resultados: AnalysisResults):
    metricas = construir_metricas(resultados)
    for inicio in range(0, len(metricas), 4):
        linha = st.columns(4)
        for coluna, metrica in zip(linha, metricas[inicio : inicio + 4]):
            with coluna:
                render_card_metrica(
                    metrica["label"],
                    metrica["valor"],
                    metrica["delta"],
                    metrica["classe"],
                )


def render_diagnostico(resultados: AnalysisResults):
    render_titulo_secao(
        "Síntese técnico-atuarial",
        "Apresentação automatizada das principais evidências produzidas pela simulação sobre inadimplência, fluxo de caixa e priorização da carteira.",
    )
    colunas = st.columns(len(resultados.diagnostico))
    for coluna, insight in zip(colunas, resultados.diagnostico):
        with coluna:
            render_card_insight(
                insight["titulo"],
                insight["descricao"],
                insight["classe"],
            )
    st.markdown('<div class="diagnostic-spacer"></div>', unsafe_allow_html=True)


def calcular_resumo_governanca(df_raw: pd.DataFrame, df_atual: pd.DataFrame) -> pd.DataFrame:
    colunas_recomendadas_presentes = sum(
        1 for coluna in RECOMMENDED_PAYMENT_COLUMNS if coluna in df_raw.columns
    )
    media_cobrancas_apolice = len(df_atual) / max(df_atual["id_apolice"].nunique(), 1)
    periodo_meses = (
        (df_atual["data_vencimento"].max().year - df_atual["data_vencimento"].min().year) * 12
        + (df_atual["data_vencimento"].max().month - df_atual["data_vencimento"].min().month)
        + 1
    )
    pagos_sem_data = int(
        df_atual["status"].eq("Pago").sum()
        - df_atual.loc[df_atual["status"].eq("Pago"), "data_pagamento"].notna().sum()
    )

    return pd.DataFrame(
        [
            {
                "Indicador": "Colunas recomendadas informadas",
                "Valor": f"{colunas_recomendadas_presentes}/{len(RECOMMENDED_PAYMENT_COLUMNS)}",
            },
            {
                "Indicador": "Período histórico observado",
                "Valor": f"{periodo_meses} meses",
            },
            {
                "Indicador": "Média de cobranças por apólice",
                "Valor": formatar_decimal(media_cobrancas_apolice),
            },
            {
                "Indicador": "Pagamentos sem data de liquidação",
                "Valor": formatar_numero(pagos_sem_data),
            },
        ]
    )


def render_aba_visao_geral(resultados: AnalysisResults):
    render_titulo_secao(
        "Comparação entre cenários",
        "Compare a carteira observada com a estimativa sob Pix Automático e examine os efeitos econômicos centrais da proposta metodológica.",
    )

    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        st.plotly_chart(
            criar_figura_ponte_premio(
                resultados.indicadores_atual,
                resultados.indicadores_pix,
            ),
            use_container_width=True,
            config=CHART_CONFIG,
        )
    with col_b:
        st.dataframe(
            montar_comparativo_formatado(resultados.comparativo),
            use_container_width=True,
            hide_index=True,
        )


def render_aba_fluxo(resultados: AnalysisResults):
    render_titulo_secao(
        "Impactos sobre o fluxo de caixa",
        "Avalie em quais períodos o Pix Automático altera o comportamento dos recebimentos e quais meios de cobrança concentram maior sensibilidade à inadimplência.",
    )

    col_a, col_b = st.columns([1.35, 1])
    with col_a:
        render_titulo_grafico("Evolução mensal do caixa")
        st.plotly_chart(
            criar_figura_fluxo(resultados.fluxo),
            use_container_width=True,
            config=CHART_CONFIG,
        )
    with col_b:
        st.plotly_chart(
            criar_figura_inadimplencia_metodo(resultados.inad_metodo),
            use_container_width=True,
            config=CHART_CONFIG,
        )


def render_aba_risco(resultados: AnalysisResults):
    render_titulo_secao(
        "Inadimplência e priorização atuarial",
        "A classificação de risco identifica concentrações de valor em aberto e aponta os grupos que melhor sustentam a adoção prioritária do Pix Automático.",
    )

    col_a, col_b = st.columns([1, 1.15])
    with col_a:
        render_titulo_grafico("Distribuição do valor em aberto")
        st.plotly_chart(
            criar_figura_risco(resultados.df_atual),
            use_container_width=True,
            config=CHART_CONFIG,
        )
    with col_b:
        render_titulo_grafico("Distribuição do índice por segmento")
        st.plotly_chart(
            criar_figura_score(resultados.df_atual),
            use_container_width=True,
            config=CHART_CONFIG,
        )

    render_titulo_grafico("Mapa de priorização da migração")
    st.plotly_chart(
        criar_figura_ranking(resultados.ranking),
        use_container_width=True,
        config=CHART_CONFIG,
    )

    ranking_exibicao = resultados.ranking.head(15).copy()
    ranking_exibicao.insert(0, "Frente", ranking_exibicao.apply(compor_frente_prioridade, axis=1))
    ranking_exibicao["recuperacao_potencial_pix"] = ranking_exibicao[
        "recuperacao_potencial_pix"
    ].map(formatar_moeda)
    ranking_exibicao["valor_em_aberto"] = ranking_exibicao["valor_em_aberto"].map(
        formatar_moeda
    )
    ranking_exibicao["score_medio"] = ranking_exibicao["score_medio"].map(formatar_decimal)
    ranking_exibicao["indice_prioridade"] = ranking_exibicao["indice_prioridade"].map(
        formatar_moeda
    )
    ranking_exibicao = ranking_exibicao.rename(
        columns={
            "apolices": "Apólices",
            "cobrancas": "Cobranças",
            "valor_em_aberto": "Valor em aberto",
            "recuperacao_potencial_pix": "Recuperação potencial com Pix",
            "score_medio": "Índice médio de risco",
            "indice_prioridade": "Índice de prioridade",
        }
    )

    colunas_uteis = [
        coluna
        for coluna in [
            "Frente",
            "Apólices",
            "Cobranças",
            "Valor em aberto",
            "Recuperação potencial com Pix",
            "Índice médio de risco",
            "Índice de prioridade",
        ]
        if coluna in ranking_exibicao.columns
    ]
    st.dataframe(
        ranking_exibicao[colunas_uteis],
        use_container_width=True,
        hide_index=True,
    )


def render_aba_dados(
    df_raw: pd.DataFrame,
    resultados: AnalysisResults,
    arquivo_origem: str,
):
    render_titulo_secao(
        "Base analítica e documentação",
        "Área de apoio à rastreabilidade do estudo, com resumo da base utilizada, documentação dos campos e exportação dos resultados da simulação.",
    )

    governanca = calcular_resumo_governanca(df_raw, resultados.df_atual)
    col_a, col_b = st.columns([0.9, 1.1])
    with col_a:
        st.dataframe(governanca, use_container_width=True, hide_index=True)
        st.caption(f"Arquivo analisado: {arquivo_origem}")
    with col_b:
        st.dataframe(montar_dicionario_colunas(), use_container_width=True, hide_index=True)

    csv_comparativo = resultados.comparativo.to_csv(index=False).encode("utf-8")
    csv_base_pix = resultados.df_pix.to_csv(index=False).encode("utf-8")
    csv_base_filtrada = resultados.df_atual.to_csv(index=False).encode("utf-8")

    col_down1, col_down2, col_down3 = st.columns(3)
    with col_down1:
        st.download_button(
            label="Baixar comparativo gerencial",
            data=csv_comparativo,
            file_name="comparativo_executivo_pix.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_down2:
        st.download_button(
            label="Baixar base estimada com Pix",
            data=csv_base_pix,
            file_name="carteira_estimada_pix.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_down3:
        st.download_button(
            label="Baixar base filtrada",
            data=csv_base_filtrada,
            file_name="carteira_filtrada.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with st.expander("Prévia da base analítica", expanded=False):
        st.dataframe(resultados.df_atual.head(100), use_container_width=True)

    with st.expander("Prévia da estimativa com Pix", expanded=False):
        st.dataframe(resultados.df_pix.head(100), use_container_width=True)


def main():
    injetar_estilos()
    template_bytes = montar_template_importacao()
    uploaded_file = render_sidebar_upload(template_bytes)

    if uploaded_file is None:
        render_hero(None, None)
        render_estado_vazio()
        st.stop()

    try:
        df_raw = carregar_base_upload(uploaded_file.name, uploaded_file.getvalue())
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

    try:
        df_base = preparar_base_pagamentos(df_raw)
    except ValueError as exc:
        st.error(str(exc))
        st.dataframe(
            pd.DataFrame({"Coluna obrigatória": REQUIRED_PAYMENT_COLUMNS}),
            use_container_width=True,
            hide_index=True,
        )
        st.stop()

    df_segmentado = aplicar_segmentacao_risco(
        df_base,
        pesos=PESOS_RISCO_PADRAO,
        limites=LIMITES_RISCO_PADRAO,
    )
    df_segmentado = padronizar_rotulos_exibicao(df_segmentado)

    filtros = render_sidebar_filtros(df_segmentado)
    df_filtrado = aplicar_filtros(df_segmentado, filtros)

    render_hero(uploaded_file.name, df_filtrado)

    if "valor_esperado" not in df_raw.columns:
        render_banner_status(
            "Campo valor_esperado não informado",
            "O prêmio esperado foi inferido a partir do histórico de pagamento. Para maior consistência metodológica da análise, recomenda-se informar valor_esperado na base original.",
            "warning",
        )

    if df_filtrado.empty:
        render_banner_status(
            "Nenhum registro no recorte atual",
            "Revise os filtros laterais para ampliar o escopo analítico.",
            "info",
        )
        st.stop()

    resultados = executar_analise(df_filtrado)

    render_metricas(resultados)
    render_diagnostico(resultados)

    aba_visao_geral, aba_fluxo, aba_risco, aba_dados = st.tabs(
        [
            "Cenários e resultados",
            "Fluxo de caixa",
            "Risco e inadimplência",
            "Base e documentação",
        ]
    )

    with aba_visao_geral:
        render_aba_visao_geral(resultados)

    with aba_fluxo:
        render_aba_fluxo(resultados)

    with aba_risco:
        render_aba_risco(resultados)

    with aba_dados:
        render_aba_dados(df_raw, resultados, uploaded_file.name)


main()
