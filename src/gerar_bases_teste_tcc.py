from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"


@dataclass(frozen=True)
class ScenarioConfig:
    slug: str
    n_apolices: int
    meses: int
    seed: int
    perfil_probs: tuple[float, float, float]
    ramo_probs: dict[str, float]
    metodo_multipliers: dict[str, float]
    inadimplencia_multiplier: float
    parcial_prob: float
    sazonalidade_alta: tuple[int, ...]
    sazonalidade_factor: float
    premio_intervalo: tuple[float, float]


BASE_METHOD_DISTRIBUTION = {
    "Bom": {"Boleto": 0.28, "Cartao": 0.34, "Debito": 0.38},
    "Medio": {"Boleto": 0.48, "Cartao": 0.28, "Debito": 0.24},
    "Ruim": {"Boleto": 0.68, "Cartao": 0.18, "Debito": 0.14},
}

BASE_INADIMPLENCIA = {
    "Bom": (0.018, [0, 1, 2, 4], [0.80, 0.12, 0.06, 0.02]),
    "Medio": (0.070, [0, 3, 7, 12], [0.56, 0.22, 0.14, 0.08]),
    "Ruim": (0.205, [0, 7, 15, 28], [0.34, 0.24, 0.25, 0.17]),
}

METHOD_RISK_MULTIPLIER = {
    "Boleto": 1.22,
    "Cartao": 0.86,
    "Debito": 0.66,
}

RAMO_RISK_MULTIPLIER = {
    "Auto": 1.08,
    "Vida": 0.90,
    "Residencial": 0.84,
    "Saude": 1.00,
    "Empresarial": 1.15,
}

SCENARIOS = [
    ScenarioConfig(
        slug="base_tcc_equilibrada",
        n_apolices=1400,
        meses=18,
        seed=101,
        perfil_probs=(0.52, 0.33, 0.15),
        ramo_probs={
            "Auto": 0.36,
            "Vida": 0.24,
            "Residencial": 0.18,
            "Saude": 0.14,
            "Empresarial": 0.08,
        },
        metodo_multipliers={"Boleto": 1.00, "Cartao": 1.00, "Debito": 1.00},
        inadimplencia_multiplier=1.00,
        parcial_prob=0.11,
        sazonalidade_alta=(1, 12),
        sazonalidade_factor=1.15,
        premio_intervalo=(120.0, 980.0),
    ),
    ScenarioConfig(
        slug="base_tcc_pressao_boleto",
        n_apolices=1800,
        meses=18,
        seed=202,
        perfil_probs=(0.30, 0.34, 0.36),
        ramo_probs={
            "Auto": 0.30,
            "Vida": 0.14,
            "Residencial": 0.16,
            "Saude": 0.12,
            "Empresarial": 0.28,
        },
        metodo_multipliers={"Boleto": 1.35, "Cartao": 0.82, "Debito": 0.76},
        inadimplencia_multiplier=1.30,
        parcial_prob=0.18,
        sazonalidade_alta=(1, 2, 12),
        sazonalidade_factor=1.32,
        premio_intervalo=(180.0, 1450.0),
    ),
    ScenarioConfig(
        slug="base_tcc_carteira_digital",
        n_apolices=1600,
        meses=18,
        seed=303,
        perfil_probs=(0.68, 0.24, 0.08),
        ramo_probs={
            "Auto": 0.22,
            "Vida": 0.28,
            "Residencial": 0.22,
            "Saude": 0.20,
            "Empresarial": 0.08,
        },
        metodo_multipliers={"Boleto": 0.74, "Cartao": 1.12, "Debito": 1.22},
        inadimplencia_multiplier=0.68,
        parcial_prob=0.07,
        sazonalidade_alta=(1, 12),
        sazonalidade_factor=1.08,
        premio_intervalo=(90.0, 860.0),
    ),
]


def gerar_base_teste_rapido() -> pd.DataFrame:
    competencias = pd.date_range("2025-01-01", periods=6, freq="MS")
    apolices = [
        {
            "id_apolice": "AP-1001",
            "id_segurado": "SEG-001",
            "ramo": "Auto",
            "perfil_pagamento": "Pontual",
            "metodo_pagamento": "Boleto",
            "valor_esperado": 540.0,
            "dia_vencimento": 10,
            "padrao": [(1.0, 0), (1.0, 3), (1.0, 0), (0.0, None), (1.0, 2), (1.0, 0)],
        },
        {
            "id_apolice": "AP-1002",
            "id_segurado": "SEG-002",
            "ramo": "Auto",
            "perfil_pagamento": "Oscilante",
            "metodo_pagamento": "Boleto",
            "valor_esperado": 620.0,
            "dia_vencimento": 12,
            "padrao": [(1.0, 5), (0.5, 8), (0.0, None), (1.0, 7), (0.75, 4), (0.0, None)],
        },
        {
            "id_apolice": "AP-1003",
            "id_segurado": "SEG-003",
            "ramo": "Vida",
            "perfil_pagamento": "Pontual",
            "metodo_pagamento": "Cartao",
            "valor_esperado": 320.0,
            "dia_vencimento": 8,
            "padrao": [(1.0, 0), (1.0, 0), (1.0, 2), (1.0, 0), (1.0, 0), (1.0, 1)],
        },
        {
            "id_apolice": "AP-1004",
            "id_segurado": "SEG-004",
            "ramo": "Vida",
            "perfil_pagamento": "Oscilante",
            "metodo_pagamento": "Cartao",
            "valor_esperado": 410.0,
            "dia_vencimento": 15,
            "padrao": [(1.0, 10), (1.0, 0), (0.0, None), (0.5, 5), (1.0, 3), (1.0, 0)],
        },
        {
            "id_apolice": "AP-1005",
            "id_segurado": "SEG-005",
            "ramo": "Residencial",
            "perfil_pagamento": "Pontual",
            "metodo_pagamento": "Debito",
            "valor_esperado": 280.0,
            "dia_vencimento": 5,
            "padrao": [(1.0, 0), (1.0, 0), (1.0, 0), (1.0, 1), (1.0, 0), (1.0, 0)],
        },
        {
            "id_apolice": "AP-1006",
            "id_segurado": "SEG-006",
            "ramo": "Residencial",
            "perfil_pagamento": "Critico",
            "metodo_pagamento": "Debito",
            "valor_esperado": 350.0,
            "dia_vencimento": 18,
            "padrao": [(0.0, None), (1.0, 4), (0.0, None), (0.5, 6), (1.0, 2), (0.0, None)],
        },
        {
            "id_apolice": "AP-1007",
            "id_segurado": "SEG-007",
            "ramo": "Empresarial",
            "perfil_pagamento": "Critico",
            "metodo_pagamento": "Boleto",
            "valor_esperado": 890.0,
            "dia_vencimento": 20,
            "padrao": [(0.5, 8), (0.0, None), (1.0, 15), (0.0, None), (0.4, 10), (0.0, None)],
        },
        {
            "id_apolice": "AP-1008",
            "id_segurado": "SEG-008",
            "ramo": "Saude",
            "perfil_pagamento": "Oscilante",
            "metodo_pagamento": "Cartao",
            "valor_esperado": 470.0,
            "dia_vencimento": 22,
            "padrao": [(1.0, 0), (1.0, 4), (0.5, 8), (1.0, 0), (0.0, None), (1.0, 3)],
        },
        {
            "id_apolice": "AP-1009",
            "id_segurado": "SEG-009",
            "ramo": "Saude",
            "perfil_pagamento": "Oscilante",
            "metodo_pagamento": "Debito",
            "valor_esperado": 510.0,
            "dia_vencimento": 9,
            "padrao": [(1.0, 0), (1.0, 1), (1.0, 0), (0.8, 5), (1.0, 0), (0.7, 3)],
        },
        {
            "id_apolice": "AP-1010",
            "id_segurado": "SEG-010",
            "ramo": "Auto",
            "perfil_pagamento": "Oscilante",
            "metodo_pagamento": "Cartao",
            "valor_esperado": 395.0,
            "dia_vencimento": 14,
            "padrao": [(1.0, 2), (0.8, 6), (1.0, 0), (0.0, None), (1.0, 1), (1.0, 0)],
        },
        {
            "id_apolice": "AP-1011",
            "id_segurado": "SEG-011",
            "ramo": "Empresarial",
            "perfil_pagamento": "Critico",
            "metodo_pagamento": "Debito",
            "valor_esperado": 760.0,
            "dia_vencimento": 16,
            "padrao": [(0.7, 5), (1.0, 0), (0.0, None), (0.6, 7), (1.0, 2), (0.0, None)],
        },
        {
            "id_apolice": "AP-1012",
            "id_segurado": "SEG-012",
            "ramo": "Vida",
            "perfil_pagamento": "Critico",
            "metodo_pagamento": "Boleto",
            "valor_esperado": 680.0,
            "dia_vencimento": 24,
            "padrao": [(0.0, None), (0.5, 9), (0.0, None), (1.0, 12), (0.0, None), (0.5, 6)],
        },
    ]

    linhas = []
    id_pagamento = 1
    for parcela, competencia in enumerate(competencias, start=1):
        for apolice in apolices:
            vencimento = competencia + pd.Timedelta(days=apolice["dia_vencimento"] - 1)
            proporcao_pago, atraso = apolice["padrao"][parcela - 1]
            valor_pago = round(apolice["valor_esperado"] * proporcao_pago, 2)
            status = "Pago" if proporcao_pago >= 0.999 else "Inadimplente"
            data_pagamento = (
                vencimento + pd.Timedelta(days=atraso)
                if atraso is not None and valor_pago > 0
                else pd.NaT
            )

            linhas.append(
                {
                    "id_pagamento": f"PG-{id_pagamento:04d}",
                    "id_apolice": apolice["id_apolice"],
                    "id_segurado": apolice["id_segurado"],
                    "id_parcela": f"PAR-{apolice['id_apolice'][3:]}-{parcela:02d}",
                    "competencia": competencia.strftime("%Y-%m"),
                    "data_vencimento": vencimento.strftime("%Y-%m-%d"),
                    "data_pagamento": (
                        data_pagamento.strftime("%Y-%m-%d")
                        if pd.notna(data_pagamento)
                        else ""
                    ),
                    "valor_pago": f"{valor_pago:.2f}",
                    "valor_esperado": f"{apolice['valor_esperado']:.2f}",
                    "status": status,
                    "metodo_pagamento": apolice["metodo_pagamento"],
                    "ramo": apolice["ramo"],
                    "perfil_pagamento": apolice["perfil_pagamento"],
                }
            )
            id_pagamento += 1

    return pd.DataFrame(linhas)


def _weighted_choice(options: dict[str, float], rng: np.random.Generator) -> str:
    labels = list(options.keys())
    weights = np.array(list(options.values()), dtype=float)
    weights = weights / weights.sum()
    return str(rng.choice(labels, p=weights))


def _sortear_metodo_pagamento(
    perfil: str,
    scenario: ScenarioConfig,
    rng: np.random.Generator,
) -> str:
    pesos = BASE_METHOD_DISTRIBUTION[perfil].copy()
    for metodo, multiplier in scenario.metodo_multipliers.items():
        pesos[metodo] *= multiplier
    return _weighted_choice(pesos, rng)


def _parametros_inadimplencia(
    perfil: str,
    ramo: str,
    metodo_pagamento: str,
    scenario: ScenarioConfig,
) -> tuple[float, list[int], list[float]]:
    prob_base, atrasos, pesos_atrasos = BASE_INADIMPLENCIA[perfil]
    prob = (
        prob_base
        * METHOD_RISK_MULTIPLIER[metodo_pagamento]
        * RAMO_RISK_MULTIPLIER[ramo]
        * scenario.inadimplencia_multiplier
    )
    return min(prob, 0.62), atrasos, pesos_atrasos


def gerar_pagamentos_sinteticos(scenario: ScenarioConfig) -> pd.DataFrame:
    rng = np.random.default_rng(scenario.seed)
    perfis = ["Bom", "Medio", "Ruim"]
    ciclo_dias = [5, 8, 10, 12, 15, 18, 20, 25]

    apolices = []
    for idx in range(1, scenario.n_apolices + 1):
        perfil = str(rng.choice(perfis, p=scenario.perfil_probs))
        ramo = _weighted_choice(scenario.ramo_probs, rng)
        metodo_pagamento = _sortear_metodo_pagamento(perfil, scenario, rng)
        premio_mensal = round(rng.uniform(*scenario.premio_intervalo), 2)
        ciclo = int(rng.choice(ciclo_dias))
        apolices.append(
            {
                "id_apolice": f"AP-{idx:06d}",
                "id_segurado": f"SEG-{idx:06d}",
                "ramo": ramo,
                "perfil_pagamento": perfil,
                "metodo_pagamento": metodo_pagamento,
                "premio_mensal": premio_mensal,
                "ciclo_dia": ciclo,
            }
        )

    base_apolices = pd.DataFrame(apolices)
    competencias = pd.date_range("2024-01-01", periods=scenario.meses, freq="MS")

    linhas = []
    id_pagamento = 1
    for parcela, competencia in enumerate(competencias, start=1):
        for apolice in base_apolices.itertuples(index=False):
            vencimento = competencia + pd.Timedelta(days=max(apolice.ciclo_dia - 1, 0))
            prob_inadimplencia, atrasos, pesos_atrasos = _parametros_inadimplencia(
                apolice.perfil_pagamento,
                apolice.ramo,
                apolice.metodo_pagamento,
                scenario,
            )
            if vencimento.month in scenario.sazonalidade_alta:
                prob_inadimplencia = min(prob_inadimplencia * scenario.sazonalidade_factor, 0.78)

            inadimplente = bool(rng.random() < prob_inadimplencia)
            valor_esperado = float(apolice.premio_mensal)

            if inadimplente:
                pagamento_parcial = bool(rng.random() < scenario.parcial_prob)
                valor_pago = (
                    round(valor_esperado * rng.uniform(0.18, 0.72), 2)
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
                    "id_pagamento": f"PG-{scenario.slug[-4:]}-{id_pagamento:08d}",
                    "id_apolice": apolice.id_apolice,
                    "id_segurado": apolice.id_segurado,
                    "id_parcela": f"{apolice.id_apolice}-{parcela:02d}",
                    "competencia": competencia.strftime("%Y-%m"),
                    "data_vencimento": vencimento.strftime("%Y-%m-%d"),
                    "data_pagamento": (
                        data_pagamento.strftime("%Y-%m-%d")
                        if pd.notna(data_pagamento)
                        else ""
                    ),
                    "valor_pago": f"{valor_pago:.2f}",
                    "valor_esperado": f"{valor_esperado:.2f}",
                    "status": status,
                    "metodo_pagamento": apolice.metodo_pagamento,
                    "ramo": apolice.ramo,
                    "perfil_pagamento": apolice.perfil_pagamento,
                }
            )
            id_pagamento += 1

    return pd.DataFrame(linhas)


def gerar_arquivos() -> list[tuple[str, int]]:
    DATA_DIR.mkdir(exist_ok=True)
    resultados = []

    base_teste_rapido = gerar_base_teste_rapido()
    destino_rapido = DATA_DIR / "pagamentos.csv"
    base_teste_rapido.to_csv(destino_rapido, index=False)
    resultados.append((destino_rapido.name, len(base_teste_rapido)))

    for scenario in SCENARIOS:
        pagamentos = gerar_pagamentos_sinteticos(scenario)
        destino = DATA_DIR / f"{scenario.slug}.csv"
        pagamentos.to_csv(destino, index=False)
        resultados.append((destino.name, len(pagamentos)))
    return resultados


def main():
    resultados = gerar_arquivos()
    for nome_arquivo, total_linhas in resultados:
        print(f"{nome_arquivo}: {total_linhas} linhas")


if __name__ == "__main__":
    main()
