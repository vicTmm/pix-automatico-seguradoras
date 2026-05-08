import pandas as pd


def montar_fluxo_caixa_mensal(df_atual: pd.DataFrame, df_pix: pd.DataFrame) -> pd.DataFrame:
    """Build monthly cash-flow views for current portfolio and Pix estimate."""
    frames = []

    for nome_visao, df in [
        ("Atual", df_atual),
        ("Estimativa com Pix Automatico", df_pix),
    ]:
        fluxo = (
            df.groupby("mes_vencimento", dropna=False)
            .agg(
                premio_esperado=("valor_esperado", "sum"),
                premio_recebido=("valor_pago", "sum"),
                premio_inadimplente=("valor_em_aberto", "sum"),
                premio_recuperado_pix=("premio_recuperado_pix", "sum"),
            )
            .reset_index()
        )
        fluxo["visao"] = nome_visao
        frames.append(fluxo)

    return pd.concat(frames, ignore_index=True).rename(columns={"mes_vencimento": "mes"})


def inadimplencia_por_metodo(df: pd.DataFrame) -> pd.DataFrame:
    resultado = (
        df.groupby("metodo_pagamento")
        .agg(
            cobrancas=("id_apolice", "count"),
            premio_esperado=("valor_esperado", "sum"),
            premio_inadimplente=("valor_em_aberto", "sum"),
        )
        .reset_index()
    )
    resultado["taxa_inadimplencia_valor"] = (
        resultado["premio_inadimplente"] / resultado["premio_esperado"]
    ).fillna(0.0)

    return resultado.sort_values("taxa_inadimplencia_valor", ascending=False)
