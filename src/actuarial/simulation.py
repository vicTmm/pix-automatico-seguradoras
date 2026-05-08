import pandas as pd

from src.data.schema import preparar_base_pagamentos


def simular_pix_automatico(
    df: pd.DataFrame,
    taxa_recuperacao_inadimplencia: float,
    random_state: int = 42,
) -> pd.DataFrame:
    """Recover part of the unpaid premium without creating new premium."""
    base = preparar_base_pagamentos(df)
    simulado = base.copy()

    candidatos = simulado["status"].eq("Inadimplente") & simulado["valor_em_aberto"].gt(0)
    total_candidatos = int(candidatos.sum())
    total_recuperados = int(total_candidatos * taxa_recuperacao_inadimplencia)

    if total_recuperados == 0:
        return simulado

    indices_recuperados = simulado.loc[candidatos].sample(
        n=total_recuperados,
        random_state=random_state,
    ).index

    premio_recuperado = simulado.loc[indices_recuperados, "valor_em_aberto"].copy()

    simulado.loc[indices_recuperados, "valor_pago"] = (
        simulado.loc[indices_recuperados, "valor_pago"] + premio_recuperado
    )
    simulado.loc[indices_recuperados, "premio_recuperado_pix"] = premio_recuperado
    simulado.loc[indices_recuperados, "valor_em_aberto"] = 0.0
    simulado.loc[indices_recuperados, "status"] = "Pago"
    simulado.loc[indices_recuperados, "metodo_pagamento"] = "Pix Automatico"
    simulado.loc[indices_recuperados, "data_pagamento"] = simulado.loc[
        indices_recuperados,
        "data_vencimento",
    ]
    simulado.loc[indices_recuperados, "recuperado_pix"] = True

    return preparar_base_pagamentos(simulado)
