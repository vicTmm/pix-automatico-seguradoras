from dataclasses import asdict

import pandas as pd

from src.actuarial.pix_inference import estimar_recuperacao_pix_por_grupo
from src.data.schema import preparar_base_pagamentos


def simular_pix_automatico(
    df: pd.DataFrame,
    taxa_recuperacao_inadimplencia: float | None = None,
    random_state: int = 42,
    return_metadata: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, dict[str, float]]:
    """Recover part of the unpaid premium without creating new premium."""
    base = preparar_base_pagamentos(df)
    simulado = base.copy()

    if taxa_recuperacao_inadimplencia is not None:
        candidatos = simulado["status"].eq("Inadimplente") & simulado["valor_em_aberto"].gt(0)
        total_candidatos = int(candidatos.sum())
        total_recuperados = int(total_candidatos * taxa_recuperacao_inadimplencia)

        if total_recuperados == 0:
            resultado = simulado
            metadata = {
                "taxa_recuperacao_inferida": float(taxa_recuperacao_inadimplencia),
                "recuperacao_potencial_total": 0.0,
                "taxa_recebimento_atual": 0.0,
                "taxa_referencia_digital": 0.0,
                "grupos_com_potencial": 0,
            }
            return (resultado, metadata) if return_metadata else resultado

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
        resultado = preparar_base_pagamentos(simulado)
        metadata = {
            "taxa_recuperacao_inferida": float(taxa_recuperacao_inadimplencia),
            "recuperacao_potencial_total": float(premio_recuperado.sum()),
            "taxa_recebimento_atual": 0.0,
            "taxa_referencia_digital": 0.0,
            "grupos_com_potencial": total_recuperados,
        }
        return (resultado, metadata) if return_metadata else resultado

    estimativas_grupo, resumo = estimar_recuperacao_pix_por_grupo(base)
    dimensoes = []
    if "ramo" in base.columns:
        dimensoes.append("ramo")
    if "segmento_risco" in base.columns:
        dimensoes.append("segmento_risco")

    merge_cols = dimensoes + ["metodo_pagamento"]
    simulado = simulado.merge(
        estimativas_grupo[merge_cols + ["proporcao_recuperacao_pix_grupo"]],
        on=merge_cols,
        how="left",
    )
    simulado["proporcao_recuperacao_pix_grupo"] = simulado[
        "proporcao_recuperacao_pix_grupo"
    ].fillna(0.0)
    simulado["premio_recuperado_pix"] = (
        simulado["valor_em_aberto"] * simulado["proporcao_recuperacao_pix_grupo"]
    ).clip(lower=0.0)
    simulado["valor_pago"] = simulado["valor_pago"] + simulado["premio_recuperado_pix"]
    simulado["valor_em_aberto"] = (
        simulado["valor_em_aberto"] - simulado["premio_recuperado_pix"]
    ).clip(lower=0.0)

    recuperados = simulado["premio_recuperado_pix"].gt(0)
    simulado.loc[recuperados, "metodo_pagamento"] = "Pix Automatico"
    simulado.loc[recuperados, "data_pagamento"] = simulado.loc[recuperados, "data_vencimento"]
    simulado.loc[simulado["valor_em_aberto"].le(0.01), "status"] = "Pago"
    simulado.loc[simulado["valor_em_aberto"].le(0.01), "valor_em_aberto"] = 0.0
    simulado.loc[recuperados, "recuperado_pix"] = True
    simulado = simulado.drop(columns=["proporcao_recuperacao_pix_grupo"])

    resultado = preparar_base_pagamentos(simulado)
    metadata = asdict(resumo)
    return (resultado, metadata) if return_metadata else resultado
