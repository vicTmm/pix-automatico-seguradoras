from pathlib import Path
import sys

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.actuarial.cashflow import inadimplencia_por_metodo
from src.actuarial.metrics import calcular_indicadores_atuariais
from src.conectar_banco import conectar_banco
from src.data.schema import preparar_base_pagamentos


def carregar_pagamentos_banco() -> pd.DataFrame:
    conn = conectar_banco()
    pagamentos = pd.read_sql_query("SELECT * FROM pagamentos", conn)
    conn.close()

    return preparar_base_pagamentos(pagamentos)


def calcular_indicadores(
    taxa_cancelamento: float | None = None,
    taxa_desconto_anual: float | None = None,
) -> dict[str, float]:
    pagamentos = carregar_pagamentos_banco()

    return calcular_indicadores_atuariais(
        pagamentos,
        taxa_cancelamento,
        taxa_desconto_anual,
    )


def resumo_inadimplencia_por_metodo() -> pd.DataFrame:
    pagamentos = carregar_pagamentos_banco()

    return inadimplencia_por_metodo(pagamentos)


if __name__ == "__main__":
    resultado = calcular_indicadores()

    for indicador, valor in resultado.items():
        print(f"{indicador}: {valor}")

    print("\n=== INADIMPLENCIA POR METODO ===\n")
    print(resumo_inadimplencia_por_metodo())
