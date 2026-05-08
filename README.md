# Pix Automatico em Seguradoras

Ferramenta atuarial de apoio a decisao desenvolvida como TCC em Ciencias Atuariais. O projeto utiliza Python, SQLite, Pandas, Plotly e Streamlit para avaliar impactos potenciais do Pix Automatico na recuperacao de premio inadimplente em seguradoras brasileiras.

## Objetivo

A seguradora importa sua base de pagamentos e a ferramenta entrega automaticamente uma leitura atuarial da carteira:

- indicadores de inadimplencia por quantidade e valor;
- persistencia estimada da carteira;
- cancelamentos estimados;
- fluxo de caixa mensal;
- valor presente dos recebimentos;
- score de risco de inadimplencia por apolice;
- ranking de grupos prioritarios para migracao ao Pix Automatico.

## Premissa atuarial central

A ferramenta nao assume criacao de receita nova pelo Pix.

```text
Premio esperado
(-) premio inadimplente
(+) premio recuperado com Pix
= premio recebido estimado
```

O Pix Automatico atua como mecanismo de recuperacao de valores em aberto. A metodologia e aplicada automaticamente; o usuario nao precisa ajustar filtros ou premissas no dashboard.

## Estrutura minima da base

A base importada deve conter:

- `id_apolice`
- `data_vencimento`
- `data_pagamento`
- `valor_pago`
- `status`
- `metodo_pagamento`

Colunas recomendadas para bases reais:

- `id_pagamento`
- `id_segurado`
- `id_parcela`
- `competencia`
- `ramo`
- `perfil_pagamento`
- `valor_esperado`

Quando `valor_esperado` nao existir, a ferramenta infere o premio esperado pelo historico pago da apolice ou pela media paga da carteira. Para bases reais de seguradoras, recomenda-se enviar `valor_esperado` explicitamente.

## Base sintetica

O gerador atual cria varias competencias mensais por apolice, permitindo analise de recorrencia, atraso, frequencia de inadimplencia, persistencia e fluxo de caixa.

```powershell
python src\gerar_base_sintetica.py --apolices 5000 --meses 24 --seed 42
```

Esse comando atualiza:

- `database/dados.db`
- `data/pagamentos.csv`

## Score de risco

O score de inadimplencia e calculado automaticamente por apolice e varia de 0 a 100. Ele combina:

- quantidade de atrasos;
- frequencia de inadimplencia;
- dias medios de atraso;
- valor em aberto;
- risco associado ao metodo de pagamento.

## Executar dashboard

```powershell
python -m streamlit run app\streamlit_app.py
```

## Testes

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Autor

Victor Hugo Araujo
