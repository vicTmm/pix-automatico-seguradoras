import pandas as pd
from conectar_banco import conectar_banco
import os

os.makedirs("data/processed", exist_ok=True)

def calcular_indicadores():
    conn = conectar_banco()

    pagamentos = pd.read_sql_query("SELECT * FROM pagamentos", conn)
    conn.close()

    total_pagamentos = len(pagamentos)
    inadimplentes = pagamentos[pagamentos["status"] == "Inadimplente"]

    taxa_inadimplencia = len(inadimplentes) / total_pagamentos
    receita_prevista = pagamentos["valor_pago"].sum() + inadimplentes.shape[0] * pagamentos["valor_pago"].mean()
    receita_recebida = pagamentos["valor_pago"].sum()
    perda_inadimplencia = receita_prevista - receita_recebida

    pagos = pagamentos[pagamentos["status"] == "Pago"].copy()
    pagos["data_vencimento"] = pd.to_datetime(pagos["data_vencimento"])
    pagos["data_pagamento"] = pd.to_datetime(pagos["data_pagamento"])
    pagos["dias_atraso"] = (pagos["data_pagamento"] - pagos["data_vencimento"]).dt.days

    atraso_medio = pagos["dias_atraso"].mean()

    indicadores = {
        "Total de pagamentos": total_pagamentos,
        "Taxa de inadimplência": taxa_inadimplencia,
        "Receita recebida": receita_recebida,
        "Perda estimada por inadimplência": perda_inadimplencia,
        "Atraso médio em dias": atraso_medio,
    }

    return indicadores


if __name__ == "__main__":
    resultado = calcular_indicadores()

    for indicador, valor in resultado.items():
        print(f"{indicador}: {valor}")

        import matplotlib.pyplot as plt


def gerar_graficos():
    from simulacao_pix import comparar_cenarios

    resultado = comparar_cenarios()

    # -----------------------
    # Gráfico de Receita
    # -----------------------
    receitas = [resultado["Receita Original"], resultado["Receita com Pix"]]

    plt.figure()
    plt.bar(["Sem Pix", "Com Pix"], receitas)
    plt.title("Comparação de Receita")
    plt.ylabel("Valor (R$)")
    plt.savefig("data/processed/grafico_receita.png")

    # -----------------------
    # Gráfico de Inadimplência
    # -----------------------
    inad = [resultado["Inadimplência Original"], resultado["Inadimplência com Pix"]]

    plt.figure()
    plt.bar(["Sem Pix", "Com Pix"], inad)
    plt.title("Comparação de Inadimplência")
    plt.ylabel("Taxa")
    plt.savefig("data/processed/grafico_inadimplencia.png")

    print("Gráficos gerados com sucesso!")


if __name__ == "__main__":
    gerar_graficos()