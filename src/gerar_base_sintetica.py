from pathlib import Path
import argparse
import sys

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from src.conectar_banco import conectar_banco


def _sortear_metodo_pagamento(perfil: str, rng: np.random.Generator) -> str:
    if perfil == "Bom":
        return rng.choice(["Boleto", "Cartao", "Debito"], p=[0.35, 0.35, 0.30])

    if perfil == "Medio":
        return rng.choice(["Boleto", "Cartao", "Debito"], p=[0.50, 0.30, 0.20])

    return rng.choice(["Boleto", "Cartao", "Debito"], p=[0.70, 0.20, 0.10])


def _parametros_inadimplencia(perfil: str, metodo_pagamento: str) -> tuple[float, list[int], list[float]]:
    parametros = {
        "Bom": (0.015, [0, 1, 2, 5], [0.78, 0.14, 0.06, 0.02]),
        "Medio": (0.060, [0, 3, 7, 12], [0.55, 0.23, 0.15, 0.07]),
        "Ruim": (0.180, [0, 7, 15, 25], [0.35, 0.25, 0.25, 0.15]),
    }
    multiplicador_metodo = {
        "Boleto": 1.25,
        "Cartao": 0.85,
        "Debito": 0.65,
    }

    prob_inadimplencia, atrasos, pesos_atrasos = parametros[perfil]
    prob_inadimplencia *= multiplicador_metodo[metodo_pagamento]

    return min(prob_inadimplencia, 0.45), atrasos, pesos_atrasos


def gerar_dados(n_apolices: int = 5_000, meses: int = 24, seed: int = 42):
    rng = np.random.default_rng(seed)

    apolices = pd.DataFrame(
        {
            "id_apolice": range(1, n_apolices + 1),
            "id_segurado": range(1, n_apolices + 1),
            "ramo": rng.choice(["Auto", "Vida", "Residencial"], n_apolices, p=[0.50, 0.30, 0.20]),
            "premio_mensal": rng.uniform(80, 650, n_apolices).round(2),
            "data_inicio": pd.to_datetime("2024-01-01"),
            "data_fim": pd.to_datetime("2025-12-31"),
        }
    )

    segurados = pd.DataFrame(
        {
            "id_segurado": range(1, n_apolices + 1),
            "idade": rng.integers(18, 80, n_apolices),
            "renda_mensal": rng.uniform(1_500, 20_000, n_apolices).round(2),
            "perfil_pagamento": rng.choice(
                ["Bom", "Medio", "Ruim"],
                n_apolices,
                p=[0.55, 0.30, 0.15],
            ),
        }
    )

    apolices = apolices.merge(segurados[["id_segurado", "perfil_pagamento"]], on="id_segurado")
    apolices["metodo_pagamento"] = [
        _sortear_metodo_pagamento(perfil, rng) for perfil in apolices["perfil_pagamento"]
    ]

    vencimentos = pd.date_range("2024-01-01", periods=meses, freq="MS") + pd.Timedelta(days=9)
    linhas = []
    id_pagamento = 1

    for parcela, vencimento in enumerate(vencimentos, start=1):
        fator_sazonal = 1.15 if vencimento.month in [1, 12] else 1.0

        for apolice in apolices.itertuples(index=False):
            prob_inadimplencia, atrasos, pesos_atrasos = _parametros_inadimplencia(
                apolice.perfil_pagamento,
                apolice.metodo_pagamento,
            )
            inadimplente = rng.random() < min(prob_inadimplencia * fator_sazonal, 0.60)
            valor_esperado = float(apolice.premio_mensal)

            if inadimplente:
                pagamento_parcial = rng.random() < 0.12
                valor_pago = (
                    round(valor_esperado * rng.uniform(0.20, 0.70), 2)
                    if pagamento_parcial
                    else 0.0
                )
                data_pagamento = pd.NaT
                status = "Inadimplente"
            else:
                atraso = int(rng.choice(atrasos, p=pesos_atrasos))
                valor_pago = valor_esperado
                data_pagamento = vencimento + pd.Timedelta(days=atraso)
                status = "Pago"

            linhas.append(
                {
                    "id_pagamento": id_pagamento,
                    "id_apolice": apolice.id_apolice,
                    "id_segurado": apolice.id_segurado,
                    "id_parcela": parcela,
                    "competencia": vencimento.strftime("%Y-%m"),
                    "ramo": apolice.ramo,
                    "perfil_pagamento": apolice.perfil_pagamento,
                    "data_vencimento": vencimento,
                    "data_pagamento": data_pagamento,
                    "valor_esperado": valor_esperado,
                    "valor_pago": valor_pago,
                    "status": status,
                    "metodo_pagamento": apolice.metodo_pagamento,
                }
            )
            id_pagamento += 1

    pagamentos = pd.DataFrame(linhas)
    apolices = apolices.drop(columns=["perfil_pagamento", "metodo_pagamento"])

    return apolices, segurados, pagamentos


def salvar_no_banco(
    n_apolices: int = 5_000,
    meses: int = 24,
    exportar_csv: bool = True,
    seed: int = 42,
):
    conn = conectar_banco()
    apolices, segurados, pagamentos = gerar_dados(
        n_apolices=n_apolices,
        meses=meses,
        seed=seed,
    )

    apolices.to_sql("apolices", conn, if_exists="replace", index=False)
    segurados.to_sql("segurados", conn, if_exists="replace", index=False)
    pagamentos.to_sql("pagamentos", conn, if_exists="replace", index=False)
    conn.close()

    if exportar_csv:
        data_dir = ROOT_DIR / "data"
        data_dir.mkdir(exist_ok=True)
        pagamentos.to_csv(data_dir / "pagamentos.csv", index=False)

    print(
        f"Base sintetica gerada: {len(apolices)} apolices, "
        f"{len(pagamentos)} pagamentos, {meses} competencias."
    )


def main():
    parser = argparse.ArgumentParser(description="Gera base sintetica atuarial recorrente.")
    parser.add_argument("--apolices", type=int, default=5_000)
    parser.add_argument("--meses", type=int, default=24)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sem-csv", action="store_true")
    args = parser.parse_args()

    salvar_no_banco(
        n_apolices=args.apolices,
        meses=args.meses,
        exportar_csv=not args.sem_csv,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
