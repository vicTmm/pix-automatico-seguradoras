from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.actuarial.metrics import calcular_indicadores_atuariais
from src.actuarial.simulation import simular_pix_automatico
from src.conectar_banco import conectar_banco
from src.data.schema import preparar_base_pagamentos


def carregar_pagamentos_banco() -> pd.DataFrame:
    conn = conectar_banco()
    pagamentos = pd.read_sql_query("SELECT * FROM pagamentos", conn)
    conn.close()

    return preparar_base_pagamentos(pagamentos)


def simular_pix(reducao_inadimplencia: float = 0.4) -> tuple[pd.DataFrame, pd.DataFrame]:
    pagamentos = carregar_pagamentos_banco()
    pagamentos_simulados = simular_pix_automatico(pagamentos, reducao_inadimplencia)

    return pagamentos, pagamentos_simulados


def montar_comparativo_atuarial(
    reducao_inadimplencia: float = 0.4,
    taxa_cancelamento: float = 0.25,
    taxa_desconto_anual: float = 0.10,
) -> dict[str, float]:
    original, simulado = simular_pix(reducao_inadimplencia)

    indicadores_original = calcular_indicadores_atuariais(
        original,
        taxa_cancelamento,
        taxa_desconto_anual,
    )
    indicadores_simulado = calcular_indicadores_atuariais(
        simulado,
        taxa_cancelamento,
        taxa_desconto_anual,
    )

    return {
        "Premio esperado": indicadores_original["premio_esperado"],
        "Premio recebido original": indicadores_original["premio_recebido"],
        "Premio recebido com Pix": indicadores_simulado["premio_recebido"],
        "Premio recuperado com Pix": indicadores_simulado["premio_recuperado_pix"],
        "Premio inadimplente original": indicadores_original["premio_inadimplente"],
        "Premio inadimplente com Pix": indicadores_simulado["premio_inadimplente"],
        "Inadimplencia original": indicadores_original["taxa_inadimplencia_qtd"],
        "Inadimplencia com Pix": indicadores_simulado["taxa_inadimplencia_qtd"],
    }


if __name__ == "__main__":
    print("\n=== COMPARATIVO ATUARIAL ===\n")
    resultado = montar_comparativo_atuarial()

    for chave, valor in resultado.items():
        print(f"{chave}: {valor}")
