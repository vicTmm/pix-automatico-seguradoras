import pandas as pd

from src.actuarial.present_value import calcular_valor_presente_recebimentos


def calcular_indicadores_atuariais(
    df: pd.DataFrame,
    taxa_cancelamento_inadimplentes: float,
    taxa_desconto_anual: float,
) -> dict[str, float]:
    """Calculate the core actuarial indicators for one portfolio view."""
    total_cobrancas = len(df)
    inadimplentes = df["status"].eq("Inadimplente")
    pagos = df["status"].eq("Pago")

    premio_esperado = float(df["valor_esperado"].sum())
    premio_recebido = float(df["valor_pago"].sum())
    premio_recuperado_pix = float(df.get("premio_recuperado_pix", pd.Series(0, index=df.index)).sum())
    premio_inadimplente = float(df["valor_em_aberto"].sum())

    taxa_inadimplencia_qtd = (
        float(inadimplentes.sum() / total_cobrancas)
        if total_cobrancas
        else 0.0
    )
    taxa_inadimplencia_valor = (
        float(premio_inadimplente / premio_esperado)
        if premio_esperado
        else 0.0
    )

    cancelamentos_estimados = float(inadimplentes.sum() * taxa_cancelamento_inadimplentes)
    taxa_cancelamento_estimada = (
        float(cancelamentos_estimados / total_cobrancas)
        if total_cobrancas
        else 0.0
    )
    persistencia_estimada = max(0.0, 1 - taxa_cancelamento_estimada)

    atraso_medio = float(df.loc[pagos, "dias_atraso"].mean()) if pagos.any() else 0.0
    valor_presente = calcular_valor_presente_recebimentos(df, taxa_desconto_anual)

    return {
        "premio_esperado": premio_esperado,
        "premio_recebido": premio_recebido,
        "premio_inadimplente": premio_inadimplente,
        "premio_recuperado_pix": premio_recuperado_pix,
        "taxa_inadimplencia_qtd": taxa_inadimplencia_qtd,
        "taxa_inadimplencia_valor": taxa_inadimplencia_valor,
        "persistencia_estimada": persistencia_estimada,
        "cancelamentos_estimados": cancelamentos_estimados,
        "atraso_medio": atraso_medio,
        "valor_presente_recebimentos": valor_presente,
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
        "persistencia_estimada": "Persistencia estimada",
        "cancelamentos_estimados": "Cancelamentos estimados",
        "atraso_medio": "Atraso medio",
        "valor_presente_recebimentos": "Valor presente dos recebimentos",
    }

    return pd.DataFrame(
        {
            "Indicador": list(labels.values()),
            "Carteira atual": [indicadores_atual[key] for key in labels],
            "Estimativa com Pix Automatico": [indicadores_pix[key] for key in labels],
            "Variacao": [indicadores_pix[key] - indicadores_atual[key] for key in labels],
        }
    )
