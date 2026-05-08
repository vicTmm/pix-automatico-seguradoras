import unittest

import pandas as pd

from src.actuarial.metrics import calcular_indicadores_atuariais
from src.actuarial.risk import (
    RiskScoreWeights,
    calcular_score_risco_inadimplencia,
    aplicar_segmentacao_risco,
)
from src.actuarial.simulation import simular_pix_automatico
from src.data.schema import preparar_base_pagamentos


class ActuarialLogicTest(unittest.TestCase):
    def setUp(self):
        self.base = pd.DataFrame(
            {
                "id_apolice": [1, 2, 3, 4],
                "data_vencimento": [
                    "2024-01-10",
                    "2024-01-10",
                    "2024-02-10",
                    "2024-02-10",
                ],
                "data_pagamento": [
                    "2024-01-10",
                    None,
                    "2024-02-20",
                    None,
                ],
                "valor_esperado": [100.0, 200.0, 150.0, 100.0],
                "valor_pago": [100.0, 0.0, 150.0, 50.0],
                "status": ["Pago", "Inadimplente", "Pago", "Inadimplente"],
                "metodo_pagamento": ["Boleto", "Boleto", "Cartao", "Debito"],
            }
        )

    def test_pix_recupera_premio_em_aberto_sem_criar_receita_nova(self):
        atual = preparar_base_pagamentos(self.base)
        simulado = simular_pix_automatico(atual, taxa_recuperacao_inadimplencia=1.0)

        indicadores_atual = calcular_indicadores_atuariais(atual, 0.25, 0.10)
        indicadores_pix = calcular_indicadores_atuariais(simulado, 0.25, 0.10)

        self.assertEqual(indicadores_atual["premio_esperado"], indicadores_pix["premio_esperado"])
        self.assertEqual(indicadores_atual["premio_inadimplente"], 250.0)
        self.assertEqual(indicadores_pix["premio_recuperado_pix"], 250.0)
        self.assertEqual(indicadores_pix["premio_inadimplente"], 0.0)
        self.assertEqual(
            indicadores_pix["premio_recebido"],
            indicadores_atual["premio_recebido"] + indicadores_pix["premio_recuperado_pix"],
        )

    def test_indicadores_calculam_inadimplencia_por_quantidade_e_valor(self):
        atual = preparar_base_pagamentos(self.base)
        indicadores = calcular_indicadores_atuariais(atual, 0.25, 0.10)

        self.assertEqual(indicadores["taxa_inadimplencia_qtd"], 0.5)
        self.assertEqual(indicadores["taxa_inadimplencia_valor"], 250.0 / 550.0)
        self.assertEqual(indicadores["atraso_medio"], 5.0)

    def test_segmentacao_de_risco_adiciona_score_interpretavel(self):
        atual = preparar_base_pagamentos(self.base)
        segmentado = aplicar_segmentacao_risco(atual)

        self.assertIn("score_inadimplencia", segmentado.columns)
        self.assertIn("segmento_risco", segmentado.columns)
        self.assertTrue(segmentado["score_inadimplencia"].between(0, 100).all())

    def test_pesos_do_score_sao_normalizados(self):
        pesos = RiskScoreWeights(
            quantidade_atrasos=10,
            frequencia_inadimplencia=20,
            dias_medios_atraso=0,
            valor_em_aberto=20,
            metodo_pagamento=0,
        ).normalizados()

        self.assertAlmostEqual(sum(pesos.values()), 1.0)
        self.assertAlmostEqual(pesos["frequencia_inadimplencia"], 0.4)

    def test_score_calibrado_por_valor_em_aberto_prioriza_maior_exposicao(self):
        atual = preparar_base_pagamentos(self.base)
        score = calcular_score_risco_inadimplencia(
            atual,
            pesos=RiskScoreWeights(
                quantidade_atrasos=0,
                frequencia_inadimplencia=0,
                dias_medios_atraso=0,
                valor_em_aberto=100,
                metodo_pagamento=0,
            ),
        ).set_index("id_apolice")

        self.assertGreater(
            score.loc[2, "score_inadimplencia"],
            score.loc[4, "score_inadimplencia"],
        )
        self.assertGreater(
            score.loc[4, "score_inadimplencia"],
            score.loc[1, "score_inadimplencia"],
        )


if __name__ == "__main__":
    unittest.main()
