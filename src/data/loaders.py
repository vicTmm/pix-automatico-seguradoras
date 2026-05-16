from pathlib import Path

import pandas as pd


def carregar_arquivo_pagamentos(file) -> pd.DataFrame:
    """Load an uploaded CSV or Excel file into a DataFrame."""
    filename = file.name.lower()

    if filename.endswith(".csv"):
        return pd.read_csv(file)

    if filename.endswith((".xlsx", ".xls")):
        return pd.read_excel(file)

    raise ValueError("Formato de arquivo não suportado.")


def carregar_csv_local(path: str | Path) -> pd.DataFrame:
    """Load a local CSV file used as sample or fallback data."""
    return pd.read_csv(path)
