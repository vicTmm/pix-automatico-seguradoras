import pandas as pd


def calcular_valor_presente_recebimentos(df: pd.DataFrame, taxa_desconto_anual: float) -> float:
    """Discount received cash flows using monthly compounding."""
    if df.empty:
        return 0.0

    data_base = df["data_vencimento"].min()

    if pd.isna(data_base):
        return 0.0

    taxa_mensal = (1 + taxa_desconto_anual) ** (1 / 12) - 1
    data_recebimento = df["data_pagamento"].fillna(df["data_vencimento"])

    meses_ate_recebimento = (
        (data_recebimento.dt.year - data_base.year) * 12
        + (data_recebimento.dt.month - data_base.month)
    ).clip(lower=0)

    fator_desconto = (1 + taxa_mensal) ** meses_ate_recebimento
    valor_presente = df["valor_pago"].fillna(0.0) / fator_desconto

    return float(valor_presente.sum())
