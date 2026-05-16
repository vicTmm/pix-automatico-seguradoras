import pandas as pd


REQUIRED_PAYMENT_COLUMNS = [
    "id_apolice",
    "data_vencimento",
    "data_pagamento",
    "valor_pago",
    "status",
    "metodo_pagamento",
]

VALID_STATUS = {"Pago", "Inadimplente"}


def validar_schema_pagamentos(df: pd.DataFrame) -> list[str]:
    """Return required columns that are missing from the payment base."""
    return [column for column in REQUIRED_PAYMENT_COLUMNS if column not in df.columns]


def _normalizar_status(series: pd.Series) -> pd.Series:
    status = series.fillna("").astype(str).str.strip()
    status_lower = status.str.lower()

    return status_lower.map(
        {
            "pago": "Pago",
            "inadimplente": "Inadimplente",
        }
    ).fillna(status)


def _inferir_valor_esperado(df: pd.DataFrame) -> pd.Series:
    if "valor_esperado" in df.columns:
        return pd.to_numeric(df["valor_esperado"], errors="coerce")

    if "premio_mensal" in df.columns:
        return pd.to_numeric(df["premio_mensal"], errors="coerce")

    pagamentos_positivos = df[df["valor_pago"] > 0]
    premio_por_apolice = pagamentos_positivos.groupby("id_apolice")["valor_pago"].median()
    premio_medio_carteira = pagamentos_positivos["valor_pago"].mean()

    if pd.isna(premio_medio_carteira):
        premio_medio_carteira = 0.0

    valor_esperado = df["valor_pago"].copy()
    valor_inferido = df["id_apolice"].map(premio_por_apolice).fillna(premio_medio_carteira)
    precisa_inferencia = df["status"].eq("Inadimplente") | df["valor_pago"].le(0)

    valor_esperado.loc[precisa_inferencia] = valor_inferido.loc[precisa_inferencia]

    return valor_esperado


def preparar_base_pagamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and enrich the payment base with actuarial working columns."""
    faltantes = validar_schema_pagamentos(df)

    if faltantes:
        raise ValueError(f"Colunas obrigatórias ausentes: {', '.join(faltantes)}")

    base = df.copy()

    base["status"] = _normalizar_status(base["status"])
    base["data_vencimento"] = pd.to_datetime(base["data_vencimento"], errors="coerce")
    base["data_pagamento"] = pd.to_datetime(base["data_pagamento"], errors="coerce")
    base["valor_pago"] = pd.to_numeric(base["valor_pago"], errors="coerce").fillna(0.0)
    base["valor_esperado"] = _inferir_valor_esperado(base).fillna(base["valor_pago"])
    base["valor_esperado"] = base[["valor_esperado", "valor_pago"]].max(axis=1)

    if "premio_recuperado_pix" not in base.columns:
        base["premio_recuperado_pix"] = 0.0
    else:
        base["premio_recuperado_pix"] = pd.to_numeric(
            base["premio_recuperado_pix"],
            errors="coerce",
        ).fillna(0.0)

    if "recuperado_pix" not in base.columns:
        base["recuperado_pix"] = False
    else:
        base["recuperado_pix"] = base["recuperado_pix"].fillna(False).astype(bool)

    base["valor_em_aberto"] = (base["valor_esperado"] - base["valor_pago"]).clip(lower=0.0)
    base["mes_vencimento"] = base["data_vencimento"].dt.to_period("M").astype(str)

    dias_atraso = (base["data_pagamento"] - base["data_vencimento"]).dt.days
    base["dias_atraso"] = dias_atraso.fillna(0).clip(lower=0)
    base.loc[base["status"].eq("Inadimplente"), "dias_atraso"] = 0

    invalid_status = ~base["status"].isin(VALID_STATUS)
    if invalid_status.any():
        valores = sorted(base.loc[invalid_status, "status"].dropna().unique())
        raise ValueError(f"Status inválidos encontrados: {', '.join(valores)}")

    if base["data_vencimento"].isna().any():
        raise ValueError("Existem datas de vencimento inválidas na base.")

    return base
