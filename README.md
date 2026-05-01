# 📊 Simulador Atuarial do Pix Automático

Ferramenta desenvolvida em Python e Streamlit para simular o impacto do Pix Automático na inadimplência e no fluxo de caixa de seguradoras brasileiras.

## 🔍 Objetivo

Permitir que seguradoras analisem, com base em seus próprios dados, os ganhos potenciais da automatização de pagamentos.

## ⚙️ Funcionalidades

- Upload de base de pagamentos (CSV/Excel)
- Cálculo de indicadores (inadimplência, receita, atraso médio)
- Simulação de cenários com Pix Automático
- Comparação entre cenários
- Visualização gráfica dos resultados
- Download da base simulada

## 📁 Estrutura esperada da base

A base deve conter as seguintes colunas:

- id_apolice
- data_vencimento
- data_pagamento
- valor_pago
- status (Pago / Inadimplente)
- metodo_pagamento

## 🚀 Deploy

A aplicação está disponível em:

👉 https://pix-automatico-seguradoras-8w2snv6vm274wclkdkwarb.streamlit.app/

## 🧠 Tecnologias utilizadas

- Python
- Pandas
- SQL (SQLite)
- Streamlit
- Plotly

## 📌 Autor

Victor Hugo Araujo