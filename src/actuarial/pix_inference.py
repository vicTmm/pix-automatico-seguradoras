from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.schema import preparar_base_pagamentos


DIGITAL_REFERENCE_METHODS = {"Cartao", "Cartão", "Debito", "Débito"}


@dataclass(frozen=True)
class PixInferenceSummary:
    taxa_recuperacao_inferida: float
    recuperacao_potencial_total: float
    taxa_recebimento_atual: float
    taxa_referencia_digital: float
    grupos_com_potencial: int


def _taxa_recebimento(frame: pd.DataFrame) -> float:
    premio_esperado = float(frame["premio_esperado"].sum())
    if premio_esperado <= 0:
        return 0.0
    return float(frame["valor_pago"].sum() / premio_esperado)


def _weighted_mean(series: pd.Series, weights: pd.Series) -> float:
    pesos_validos = weights.fillna(0.0)
    total = float(pesos_validos.sum())
    if total <= 0:
        return 0.0
    return float((series.fillna(0.0) * pesos_validos).sum() / total)


def estimar_recuperacao_pix_por_grupo(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, PixInferenceSummary]:
    base = preparar_base_pagamentos(df)
    dimensoes = []

    if "ramo" in base.columns:
        dimensoes.append("ramo")
    if "segmento_risco" in base.columns:
        dimensoes.append("segmento_risco")

    group_cols = dimensoes + ["metodo_pagamento"]
    agrupado = (
        base.groupby(group_cols, dropna=False)
        .agg(
            premio_esperado=("valor_esperado", "sum"),
            valor_pago=("valor_pago", "sum"),
            valor_em_aberto=("valor_em_aberto", "sum"),
            cobrancas=("id_apolice", "count"),
        )
        .reset_index()
    )
    agrupado["taxa_recebimento_observada"] = agrupado.apply(
        lambda row: (
            float(row["valor_pago"] / row["premio_esperado"])
            if row["premio_esperado"] > 0
            else 0.0
        ),
        axis=1,
    )

    segment_cols = dimensoes.copy()
    segment_key = "__segmento_tecnico__"
    if not segment_cols:
        agrupado[segment_key] = "Carteira"
        segment_cols = [segment_key]

    digital = agrupado[agrupado["metodo_pagamento"].isin(DIGITAL_REFERENCE_METHODS)].copy()
    benchmark_segmento = None
    benchmark_geral = None

    if not digital.empty:
        benchmark_segmento = (
            digital.groupby(segment_cols)
            .apply(_taxa_recebimento)
            .rename("taxa_referencia_digital")
            .reset_index()
        )
        benchmark_geral = _taxa_recebimento(digital)

    melhor_observado = (
        agrupado.groupby(segment_cols)["taxa_recebimento_observada"]
        .max()
        .rename("taxa_melhor_observada")
        .reset_index()
    )
    agrupado = agrupado.merge(melhor_observado, on=segment_cols, how="left")

    if benchmark_segmento is not None:
        agrupado = agrupado.merge(benchmark_segmento, on=segment_cols, how="left")

    if "taxa_referencia_digital" not in agrupado.columns:
        agrupado["taxa_referencia_digital"] = pd.NA

    if benchmark_geral is None:
        benchmark_geral = float(agrupado["taxa_melhor_observada"].mean())

    agrupado["taxa_referencia_digital"] = (
        agrupado["taxa_referencia_digital"]
        .fillna(benchmark_geral)
        .fillna(agrupado["taxa_melhor_observada"])
    )
    agrupado["ganho_potencial_recebimento"] = (
        agrupado["taxa_referencia_digital"] - agrupado["taxa_recebimento_observada"]
    ).clip(lower=0.0)
    agrupado["recuperacao_potencial_pix"] = (
        agrupado["ganho_potencial_recebimento"] * agrupado["premio_esperado"]
    ).clip(lower=0.0)
    agrupado["recuperacao_potencial_pix"] = agrupado[
        ["recuperacao_potencial_pix", "valor_em_aberto"]
    ].min(axis=1)
    agrupado["proporcao_recuperacao_pix_grupo"] = agrupado.apply(
        lambda row: (
            float(row["recuperacao_potencial_pix"] / row["valor_em_aberto"])
            if row["valor_em_aberto"] > 0
            else 0.0
        ),
        axis=1,
    ).clip(lower=0.0, upper=1.0)

    total_aberto = float(agrupado["valor_em_aberto"].sum())
    total_recuperacao = float(agrupado["recuperacao_potencial_pix"].sum())
    taxa_recebimento_atual = _taxa_recebimento(agrupado)
    taxa_referencia_digital = _weighted_mean(
        agrupado["taxa_referencia_digital"],
        agrupado["premio_esperado"],
    )
    resumo = PixInferenceSummary(
        taxa_recuperacao_inferida=(
            float(total_recuperacao / total_aberto) if total_aberto > 0 else 0.0
        ),
        recuperacao_potencial_total=total_recuperacao,
        taxa_recebimento_atual=taxa_recebimento_atual,
        taxa_referencia_digital=taxa_referencia_digital,
        grupos_com_potencial=int(agrupado["recuperacao_potencial_pix"].gt(0).sum()),
    )

    if segment_key in agrupado.columns:
        agrupado = agrupado.drop(columns=[segment_key])

    return agrupado, resumo
