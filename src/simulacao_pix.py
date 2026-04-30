import pandas as pd
import numpy as np
from conectar_banco import conectar_banco


def simular_pix(reducao_inadimplencia=0.4):
    conn = conectar_banco()

    pagamentos = pd.read_sql_query("SELECT * FROM pagamentos", conn)
    conn.close()

    pagamentos_simulado = pagamentos.copy()

    # Identifica inadimplentes
    inadimplentes = pagamentos_simulado["status"] == "Inadimplente"

    # Reduz inadimplência (ex: 40%)
    n_inadimplentes = inadimplentes.sum()
    n_recuperados = int(n_inadimplentes * reducao_inadimplencia)

    indices_recuperados = pagamentos_simulado[inadimplentes].sample(n=n_recuperados, random_state=42).index

    # Transforma em pagos
    pagamentos_simulado.loc[indices_recuperados, "status"] = "Pago"
    pagamentos_simulado.loc[indices_recuperados, "valor_pago"] = np.random.uniform(50, 500, n_recuperados)

    # Atualiza método de pagamento
    pagamentos_simulado["metodo_pagamento"] = "Pix Automático"

    return pagamentos, pagamentos_simulado


def comparar_cenarios():
    original, simulado = simular_pix()

    receita_original = original["valor_pago"].sum()
    receita_simulada = simulado["valor_pago"].sum()

    inadimplencia_original = (original["status"] == "Inadimplente").mean()
    inadimplencia_simulada = (simulado["status"] == "Inadimplente").mean()

    resultado = {
        "Receita Original": receita_original,
        "Receita com Pix": receita_simulada,
        "Ganho de Receita": receita_simulada - receita_original,
        "Inadimplência Original": inadimplencia_original,
        "Inadimplência com Pix": inadimplencia_simulada
    }

    return resultado


def analise_sensibilidade():
    cenarios = [0.2, 0.4, 0.6]
    resultados = []

    for reducao in cenarios:
        original, simulado = simular_pix(reducao_inadimplencia=reducao)

        receita_original = original["valor_pago"].sum()
        receita_simulada = simulado["valor_pago"].sum()

        inadimplencia_original = (original["status"] == "Inadimplente").mean()
        inadimplencia_simulada = (simulado["status"] == "Inadimplente").mean()

        resultados.append({
            "Reducao_Inadimplencia": reducao,
            "Receita_Original": receita_original,
            "Receita_Com_Pix": receita_simulada,
            "Ganho_Receita": receita_simulada - receita_original,
            "Inadimplencia_Original": inadimplencia_original,
            "Inadimplencia_Com_Pix": inadimplencia_simulada
        })

    return pd.DataFrame(resultados)

if __name__ == "__main__":
    print("\n=== COMPARAÇÃO DE CENÁRIOS ===\n")
    resultado = comparar_cenarios()

    for k, v in resultado.items():
        print(f"{k}: {v}")

    print("\n=== ANÁLISE DE SENSIBILIDADE ===\n")
    sensibilidade = analise_sensibilidade()
    print(sensibilidade)
        