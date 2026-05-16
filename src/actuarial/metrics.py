import pandas as pd


def calcular_indicadores_atuariais(
    df: pd.DataFrame,
    taxa_cancelamento_inadimplentes: float | None = None,
    taxa_desconto_anual: float | None = None,
) -> dict[str, float]:
    """Calculate the core actuarial indicators for one portfolio view."""
    total_cobrancas = len(df)
    total_apolices = int(df["id_apolice"].nunique()) if "id_apolice" in df.columns else 0
    inadimplentes = df["status"].eq("Inadimplente")
    pagos = df["status"].eq("Pago")

    premio_esperado = float(df["valor_esperado"].sum())
    premio_recebido = float(df["valor_pago"].sum())
    premio_recuperado_pix = float(
        df.get("premio_recuperado_pix", pd.Series(0, index=df.index)).sum()
    )
    premio_inadimplente = float(df["valor_em_aberto"].sum())

    taxa_inadimplencia_qtd = (
        float(inadimplentes.sum() / total_cobrancas) if total_cobrancas else 0.0
    )
    taxa_inadimplencia_valor = (
        float(premio_inadimplente / premio_esperado) if premio_esperado else 0.0
    )

    atraso_medio = float(df.loc[pagos, "dias_atraso"].mean()) if pagos.any() else 0.0
    saldo_por_apolice = df.groupby("id_apolice")["valor_em_aberto"].sum()
    apolices_regulares = int(saldo_por_apolice.le(0.01).sum())
    apolices_com_saldo_em_aberto = float(max(total_apolices - apolices_regulares, 0))
    taxa_regularidade_carteira = (
        float(apolices_regulares / total_apolices) if total_apolices else 0.0
    )

    if taxa_cancelamento_inadimplentes is not None:
        cancelamentos_estimados = float(inadimplentes.sum() * taxa_cancelamento_inadimplentes)
        persistencia_estimada = max(
            0.0,
            1 - (cancelamentos_estimados / total_cobrancas if total_cobrancas else 0.0),
        )
    else:
        cancelamentos_estimados = apolices_com_saldo_em_aberto
        persistencia_estimada = taxa_regularidade_carteira

    return {
        "premio_esperado": premio_esperado,
        "premio_recebido": premio_recebido,
        "premio_inadimplente": premio_inadimplente,
        "premio_recuperado_pix": premio_recuperado_pix,
        "taxa_inadimplencia_qtd": taxa_inadimplencia_qtd,
        "taxa_inadimplencia_valor": taxa_inadimplencia_valor,
        "taxa_regularidade_carteira": taxa_regularidade_carteira,
        "apolices_com_saldo_em_aberto": apolices_com_saldo_em_aberto,
        "persistencia_estimada": persistencia_estimada,
        "cancelamentos_estimados": cancelamentos_estimados,
        "atraso_medio": atraso_medio,
    }


def montar_comparativo_indicadores(
    indicadores_atual: dict[str, float],
    indicadores_pix: dict[str, float],
) -> pd.DataFrame:
    labels = {
        "premio_esperado": "Premio esperado",
        "premio_recebido": "Premio recebido",
        "premio_inadimplente": "Premio inadimplente",
        "premio_recuperado_pix": "Premio recuperado com Pix",
        "taxa_inadimplencia_qtd": "Taxa de inadimplencia por quantidade",
        "taxa_inadimplencia_valor": "Taxa de inadimplencia por valor",
        "taxa_regularidade_carteira": "Taxa de regularidade da carteira",
        "apolices_com_saldo_em_aberto": "Apolices com saldo em aberto",
        "atraso_medio": "Atraso medio",
    }

    return pd.DataFrame(
        {
            "Indicador": list(labels.values()),
            "Carteira atual": [indicadores_atual[key] for key in labels],
            "Estimativa com Pix Automatico": [indicadores_pix[key] for key in labels],
            "Variacao": [indicadores_pix[key] - indicadores_atual[key] for key in labels],
        }
    )
