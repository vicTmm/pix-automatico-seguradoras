from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskScoreWeights:
    quantidade_atrasos: float = 0.25
    frequencia_inadimplencia: float = 0.25
    dias_medios_atraso: float = 0.20
    valor_em_aberto: float = 0.20
    metodo_pagamento: float = 0.10

    def normalizados(self) -> dict[str, float]:
        pesos = {
            "quantidade_atrasos": max(0.0, self.quantidade_atrasos),
            "frequencia_inadimplencia": max(0.0, self.frequencia_inadimplencia),
            "dias_medios_atraso": max(0.0, self.dias_medios_atraso),
            "valor_em_aberto": max(0.0, self.valor_em_aberto),
            "metodo_pagamento": max(0.0, self.metodo_pagamento),
        }
        total = sum(pesos.values())

        if total == 0:
            return RiskScoreWeights().normalizados()

        return {chave: valor / total for chave, valor in pesos.items()}


@dataclass(frozen=True)
class RiskSegmentationThresholds:
    baixo_risco_max: float = 35.0
    medio_risco_max: float = 70.0

    def validar(self):
        if not 0 <= self.baixo_risco_max < self.medio_risco_max <= 100:
            raise ValueError(
                "Os limites de segmentacao devem obedecer: "
                "0 <= baixo risco < medio risco <= 100."
            )


PAYMENT_METHOD_RISK = {
    "Boleto": 1.0,
    "Cartao": 0.55,
    "Cartão": 0.55,
    "Debito": 0.35,
    "Débito": 0.35,
    "Pix Automatico": 0.05,
    "Pix Automático": 0.05,
}


def _normalizar_serie(series: pd.Series) -> pd.Series:
    minimo = series.min()
    maximo = series.max()

    if pd.isna(minimo) or pd.isna(maximo) or maximo == minimo:
        return pd.Series(0.0, index=series.index)

    return (series - minimo) / (maximo - minimo)


def calcular_score_risco_inadimplencia(
    df: pd.DataFrame,
    pesos: RiskScoreWeights | None = None,
    limites: RiskSegmentationThresholds | None = None,
) -> pd.DataFrame:
    """Create an interpretable default-risk score at policy level."""
    pesos_normalizados = (pesos or RiskScoreWeights()).normalizados()
    limites = limites or RiskSegmentationThresholds()
    limites.validar()

    base = df.copy()
    base["evento_atraso"] = (base["dias_atraso"] > 0) | base["status"].eq("Inadimplente")
    base["evento_inadimplencia"] = base["status"].eq("Inadimplente")
    base["risco_metodo_pagamento"] = base["metodo_pagamento"].map(PAYMENT_METHOD_RISK).fillna(0.5)

    score = (
        base.groupby("id_apolice")
        .agg(
            quantidade_atrasos=("evento_atraso", "sum"),
            frequencia_inadimplencia=("evento_inadimplencia", "mean"),
            dias_medios_atraso=("dias_atraso", "mean"),
            valor_em_aberto=("valor_em_aberto", "sum"),
            risco_metodo_pagamento=("risco_metodo_pagamento", "mean"),
        )
        .reset_index()
    )

    score["score_quantidade_atrasos"] = _normalizar_serie(score["quantidade_atrasos"])
    score["score_frequencia_inadimplencia"] = score["frequencia_inadimplencia"]
    score["score_dias_medios_atraso"] = _normalizar_serie(score["dias_medios_atraso"])
    score["score_valor_em_aberto"] = _normalizar_serie(score["valor_em_aberto"])
    score["score_metodo_pagamento"] = score["risco_metodo_pagamento"]

    score["score_inadimplencia"] = 100 * (
        pesos_normalizados["quantidade_atrasos"] * score["score_quantidade_atrasos"]
        + pesos_normalizados["frequencia_inadimplencia"]
        * score["score_frequencia_inadimplencia"]
        + pesos_normalizados["dias_medios_atraso"] * score["score_dias_medios_atraso"]
        + pesos_normalizados["valor_em_aberto"] * score["score_valor_em_aberto"]
        + pesos_normalizados["metodo_pagamento"] * score["score_metodo_pagamento"]
    )

    score["score_inadimplencia"] = score["score_inadimplencia"].clip(lower=0, upper=100)
    score["segmento_risco"] = np.select(
        [
            score["score_inadimplencia"] < limites.baixo_risco_max,
            score["score_inadimplencia"] < limites.medio_risco_max,
        ],
        [
            "Baixo risco",
            "Medio risco",
        ],
        default="Alto risco",
    )

    return score


def aplicar_segmentacao_risco(
    df: pd.DataFrame,
    pesos: RiskScoreWeights | None = None,
    limites: RiskSegmentationThresholds | None = None,
) -> pd.DataFrame:
    score = calcular_score_risco_inadimplencia(df, pesos=pesos, limites=limites)
    colunas_score = [
        "quantidade_atrasos",
        "frequencia_inadimplencia",
        "dias_medios_atraso",
        "risco_metodo_pagamento",
        "score_quantidade_atrasos",
        "score_frequencia_inadimplencia",
        "score_dias_medios_atraso",
        "score_valor_em_aberto",
        "score_metodo_pagamento",
        "score_inadimplencia",
        "segmento_risco",
    ]
    base = df.drop(columns=[col for col in colunas_score if col in df.columns])

    return base.merge(
        score[
            [
                "id_apolice",
                "quantidade_atrasos",
                "frequencia_inadimplencia",
                "dias_medios_atraso",
                "risco_metodo_pagamento",
                "score_quantidade_atrasos",
                "score_frequencia_inadimplencia",
                "score_dias_medios_atraso",
                "score_valor_em_aberto",
                "score_metodo_pagamento",
                "score_inadimplencia",
                "segmento_risco",
            ]
        ],
        on="id_apolice",
        how="left",
    )


def ranking_prioridade_migracao_pix(
    df: pd.DataFrame,
    taxa_recuperacao_inadimplencia: float,
) -> pd.DataFrame:
    dimensoes = ["segmento_risco", "metodo_pagamento"]

    if "ramo" in df.columns:
        dimensoes.insert(0, "ramo")

    ranking = (
        df.groupby(dimensoes)
        .agg(
            cobrancas=("id_apolice", "count"),
            apolices=("id_apolice", "nunique"),
            premio_esperado=("valor_esperado", "sum"),
            valor_em_aberto=("valor_em_aberto", "sum"),
            score_medio=("score_inadimplencia", "mean"),
        )
        .reset_index()
    )

    ranking["recuperacao_potencial_pix"] = (
        ranking["valor_em_aberto"] * taxa_recuperacao_inadimplencia
    )
    ranking["indice_prioridade"] = (
        ranking["recuperacao_potencial_pix"] * (1 + ranking["score_medio"].fillna(0) / 100)
    )

    return ranking.sort_values("indice_prioridade", ascending=False)
