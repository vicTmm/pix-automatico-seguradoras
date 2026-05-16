# Proposta de Ferramenta de Simulação Atuarial para Mensuração dos Impactos do Pix Automático na Inadimplência e no Fluxo de Caixa de Seguradoras Brasileiras

Projeto desenvolvido como Trabalho de Conclusão de Curso em Ciências Atuariais. A aplicação utiliza Python, Pandas, Plotly, SQLite e Streamlit para estruturar uma simulação atuarial voltada à avaliação dos efeitos potenciais do Pix Automático sobre a inadimplência, a persistência da carteira e o fluxo de caixa de seguradoras brasileiras.

## Finalidade da ferramenta

Ao importar a base de pagamentos da seguradora, a ferramenta produz uma análise comparativa entre o cenário observado e o cenário estimado com adoção do Pix Automático, com foco em:

- inadimplência por quantidade e por valor;
- persistência estimada da carteira;
- cancelamentos estimados;
- fluxo de caixa mensal;
- valor presente dos recebimentos;
- índice de risco de inadimplência por apólice;
- priorização de grupos para adoção do Pix Automático.

## Premissa atuarial central

A ferramenta não considera criação de receita nova pelo Pix. A proposta parte da recuperação de valores já esperados pela seguradora.

```text
Prêmio esperado
(-) prêmio inadimplente
(+) prêmio recuperado com Pix
= prêmio recebido estimado
```

Assim, o Pix Automático é tratado como mecanismo de redução de inadimplência e de recomposição do fluxo de caixa, e não como fonte de prêmio adicional.

## Estrutura mínima da base

A base importada deve conter:

- `id_apolice`
- `data_vencimento`
- `data_pagamento`
- `valor_pago`
- `status`
- `metodo_pagamento`

Colunas recomendadas para análises mais robustas:

- `id_pagamento`
- `id_segurado`
- `id_parcela`
- `competencia`
- `ramo`
- `perfil_pagamento`
- `valor_esperado`

Quando `valor_esperado` não é informado, a ferramenta infere o prêmio esperado com base no histórico de pagamentos da apólice ou na média da carteira. Para maior consistência metodológica, recomenda-se informar esse campo explicitamente.

## Fluxo de utilização

1. Exportar a base oficial de pagamentos da carteira em CSV ou Excel.
2. Verificar a presença das colunas obrigatórias e, preferencialmente, de `valor_esperado` e `ramo`.
3. Carregar o arquivo na aplicação.
4. Comparar os cenários gerados e interpretar os efeitos sobre inadimplência e fluxo de caixa.
5. Exportar os resultados produzidos pela simulação.

## Contribuição da proposta

A ferramenta foi concebida para apoiar a defesa do projeto, convertendo a base observada em evidências quantitativas que permitam:

- estimar o efeito do Pix Automático sobre o recebimento de prêmios;
- identificar concentrações de inadimplência por meio de cobrança e por grupo de risco;
- observar alterações esperadas no fluxo de caixa;
- priorizar frentes de adoção com base em critérios atuariais.

## Gerador sintético

O gerador sintético permanece disponível apenas como apoio interno de desenvolvimento e testes:

```powershell
python src\gerar_base_sintetica.py --apolices 5000 --meses 24 --seed 42
```

## Executar a aplicação

```powershell
python -m streamlit run app\streamlit_app.py
```

## Testes

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Autor

Victor Hugo Araujo
