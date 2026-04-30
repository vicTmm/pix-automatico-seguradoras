import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from conectar_banco import conectar_banco

np.random.seed(42)

print("Arquivo gerar_base_sintetica.py executado")

def gerar_dados(n_apolices=100000):
    
    # ---------------------
    # APÓLICES
    # ---------------------
    apolices = pd.DataFrame({
        "id_apolice": range(1, n_apolices + 1),
        "ramo": np.random.choice(["Auto", "Vida", "Residencial"], n_apolices),
        "premio_mensal": np.random.uniform(50, 500, n_apolices),
        "data_inicio": pd.to_datetime("2023-01-01"),
        "data_fim": pd.to_datetime("2024-12-31")
    })

    # ---------------------
    # SEGURADOS
    # ---------------------
    segurados = pd.DataFrame({
        "id_segurado": range(1, n_apolices + 1),
        "idade": np.random.randint(18, 80, n_apolices),
        "renda_mensal": np.random.uniform(1000, 15000, n_apolices),
        "perfil_pagamento": np.random.choice(
            ["Bom", "Médio", "Ruim"],
            n_apolices,
            p=[0.5, 0.3, 0.2]
        )
    })

    # ---------------------
    # PAGAMENTOS
    # ---------------------
    pagamentos = []

    for i in range(n_apolices):
        vencimento = datetime(2024, 1, 10)

        perfil = segurados.loc[i, "perfil_pagamento"]

        if perfil == "Bom":
            atraso = np.random.choice([0, 1, 2], p=[0.8, 0.15, 0.05])
        elif perfil == "Médio":
            atraso = np.random.choice([0, 3, 5, 10], p=[0.5, 0.2, 0.2, 0.1])
        else:
            atraso = np.random.choice([0, 5, 15, None], p=[0.3, 0.2, 0.2, 0.3])

        if atraso is None:
            data_pagamento = None
            status = "Inadimplente"
            valor_pago = 0
        else:
            data_pagamento = vencimento + timedelta(days=int(atraso))
            status = "Pago"
            valor_pago = apolices.loc[i, "premio_mensal"]

        pagamentos.append([
            i+1,
            i+1,
            vencimento,
            data_pagamento,
            valor_pago,
            status,
            np.random.choice(["Boleto", "Cartão", "Débito"])
        ])

    pagamentos = pd.DataFrame(pagamentos, columns=[
        "id_pagamento",
        "id_apolice",
        "data_vencimento",
        "data_pagamento",
        "valor_pago",
        "status",
        "metodo_pagamento"
    ])

    return apolices, segurados, pagamentos


def salvar_no_banco():
    conn = conectar_banco()

    apolices, segurados, pagamentos = gerar_dados()

    apolices.to_sql("apolices", conn, if_exists="replace", index=False)
    segurados.to_sql("segurados", conn, if_exists="replace", index=False)
    pagamentos.to_sql("pagamentos", conn, if_exists="replace", index=False)

    conn.close()

    print("Base gerada com sucesso!")


if __name__ == "__main__":
    salvar_no_banco()