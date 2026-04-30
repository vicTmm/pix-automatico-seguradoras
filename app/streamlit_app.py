import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="Simulador Atuarial - Pix Automático",
    layout="wide"
)

st.title("Simulador Atuarial do Pix Automático para Seguradoras")

st.write(
    "Ferramenta para avaliar os impactos potenciais do Pix Automático "
    "sobre inadimplência, persistência de carteira, fluxo de caixa e valor presente dos recebimentos."
)

st.sidebar.header("Premissas Atuariais")

reducao_inadimplencia = st.sidebar.slider(
    "Redução esperada da inadimplência",
    min_value=0,
    max_value=100,
    value=40,
    step=5
) / 100

taxa_cancelamento = st.sidebar.slider(
    "Taxa estimada de cancelamento entre inadimplentes",
    min_value=0,
    max_value=100,
    value=25,
    step=5
) / 100

taxa_desconto_anual = st.sidebar.slider(
    "Taxa de desconto atuarial anual",
    min_value=0,
    max_value=30,
    value=10,
    step=1
) / 100

st.subheader("Formato esperado da base")

st.write("""
A base deve conter as seguintes colunas:

- id_apolice
- data_vencimento
- data_pagamento
- valor_pago
- status
- metodo_pagamento

O campo **status** deve conter os valores **Pago** ou **Inadimplente**.
""")

uploaded_file = st.file_uploader(
    "Importe uma base de pagamentos em CSV ou Excel",
    type=["csv", "xlsx"]
)

colunas_necessarias = [
    "id_apolice",
    "data_vencimento",
    "data_pagamento",
    "valor_pago",
    "status",
    "metodo_pagamento"
]


def carregar_base(file):
    if file.name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)


def validar_base(df):
    return [col for col in colunas_necessarias if col not in df.columns]


def preparar_datas(df):
    df = df.copy()
    df["data_vencimento"] = pd.to_datetime(df["data_vencimento"], errors="coerce")
    df["data_pagamento"] = pd.to_datetime(df["data_pagamento"], errors="coerce")
    df["mes_vencimento"] = df["data_vencimento"].dt.to_period("M").astype(str)
    return df


def calcular_valor_presente(df, taxa_anual):
    df = df.copy()

    taxa_mensal = (1 + taxa_anual) ** (1 / 12) - 1

    data_base = df["data_vencimento"].min()

    df["meses_ate_vencimento"] = (
        (df["data_vencimento"].dt.year - data_base.year) * 12
        + (df["data_vencimento"].dt.month - data_base.month)
    )

    df["fator_desconto"] = (1 + taxa_mensal) ** df["meses_ate_vencimento"]

    df["valor_presente"] = df["valor_pago"] / df["fator_desconto"]

    return df["valor_presente"].sum()


def calcular_indicadores(df, taxa_cancelamento, taxa_desconto_anual):
    total_pagamentos = len(df)

    inadimplentes = df[df["status"] == "Inadimplente"]
    pagos = df[df["status"] == "Pago"].copy()

    premio_recebido = df["valor_pago"].sum()

    premio_medio_pago = df[df["valor_pago"] > 0]["valor_pago"].mean()

    if pd.isna(premio_medio_pago):
        premio_medio_pago = 0

    premio_nao_recebido = len(inadimplentes) * premio_medio_pago
    premio_esperado = premio_recebido + premio_nao_recebido

    taxa_inadimplencia = len(inadimplentes) / total_pagamentos if total_pagamentos else 0

    cancelamentos_estimados = len(inadimplentes) * taxa_cancelamento
    taxa_cancelamento_estimada = cancelamentos_estimados / total_pagamentos if total_pagamentos else 0
    taxa_persistencia = 1 - taxa_cancelamento_estimada

    if not pagos.empty:
        pagos["dias_atraso"] = (pagos["data_pagamento"] - pagos["data_vencimento"]).dt.days
        atraso_medio = pagos["dias_atraso"].mean()
    else:
        atraso_medio = 0

    valor_presente = calcular_valor_presente(df, taxa_desconto_anual)

    return {
        "Prêmio esperado": premio_esperado,
        "Prêmio recebido": premio_recebido,
        "Prêmio não recebido": premio_nao_recebido,
        "Taxa de inadimplência": taxa_inadimplencia,
        "Atraso médio": atraso_medio,
        "Cancelamentos estimados": cancelamentos_estimados,
        "Taxa de persistência": taxa_persistencia,
        "Valor presente dos recebimentos": valor_presente
    }


def simular_pix(df, reducao):
    df_simulado = df.copy()

    inadimplentes = df_simulado["status"] == "Inadimplente"
    n_inadimplentes = inadimplentes.sum()
    n_recuperados = int(n_inadimplentes * reducao)

    if n_recuperados > 0:
        indices = df_simulado[inadimplentes].sample(
            n=n_recuperados,
            random_state=42
        ).index

        premio_medio = df_simulado[df_simulado["valor_pago"] > 0]["valor_pago"].mean()

        if pd.isna(premio_medio):
            premio_medio = 0

        df_simulado.loc[indices, "status"] = "Pago"
        df_simulado.loc[indices, "valor_pago"] = premio_medio
        df_simulado.loc[indices, "metodo_pagamento"] = "Pix Automático"
        df_simulado.loc[indices, "data_pagamento"] = df_simulado.loc[
            indices, "data_vencimento"
        ]

    return df_simulado


def fluxo_caixa_mensal(df_atual, df_pix):
    atual = df_atual.groupby("mes_vencimento")["valor_pago"].sum().reset_index()
    atual["Cenário"] = "Atual"

    pix = df_pix.groupby("mes_vencimento")["valor_pago"].sum().reset_index()
    pix["Cenário"] = "Com Pix Automático"

    fluxo = pd.concat([atual, pix], ignore_index=True)
    fluxo.rename(
        columns={"mes_vencimento": "Mês", "valor_pago": "Receita"},
        inplace=True
    )

    return fluxo


def analise_sensibilidade(df, taxa_cancelamento, taxa_desconto_anual):
    cenarios = list(range(10, 90, 10))
    resultados = []

    indicadores_base = calcular_indicadores(
        df,
        taxa_cancelamento,
        taxa_desconto_anual
    )

    for cenario in cenarios:
        df_sim = simular_pix(df, cenario / 100)
        df_sim = preparar_datas(df_sim)

        indicadores_sim = calcular_indicadores(
            df_sim,
            taxa_cancelamento,
            taxa_desconto_anual
        )

        resultados.append({
            "Redução da inadimplência": f"{cenario}%",
            "Prêmio recebido": indicadores_sim["Prêmio recebido"],
            "Ganho financeiro": indicadores_sim["Prêmio recebido"] - indicadores_base["Prêmio recebido"],
            "Taxa de inadimplência": indicadores_sim["Taxa de inadimplência"],
            "Taxa de persistência": indicadores_sim["Taxa de persistência"],
            "Valor presente": indicadores_sim["Valor presente dos recebimentos"]
        })

    return pd.DataFrame(resultados)


if uploaded_file is None:
    st.info("Importe uma base CSV ou Excel para iniciar a análise.")

else:
    df = carregar_base(uploaded_file)

    faltantes = validar_base(df)

    if faltantes:
        st.error("A base não possui as seguintes colunas obrigatórias:")
        st.write(faltantes)
        st.stop()

    df = preparar_datas(df)

    st.subheader("Prévia da base importada")
    st.dataframe(df.head())

    df_pix = simular_pix(df, reducao_inadimplencia)
    df_pix = preparar_datas(df_pix)

    indicadores_atual = calcular_indicadores(
        df,
        taxa_cancelamento,
        taxa_desconto_anual
    )

    indicadores_pix = calcular_indicadores(
        df_pix,
        taxa_cancelamento,
        taxa_desconto_anual
    )

    st.subheader("Indicadores Atuariais")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Prêmio recebido atual",
        f"R$ {indicadores_atual['Prêmio recebido']:,.2f}"
    )

    col2.metric(
        "Prêmio recebido com Pix",
        f"R$ {indicadores_pix['Prêmio recebido']:,.2f}",
        delta=f"R$ {indicadores_pix['Prêmio recebido'] - indicadores_atual['Prêmio recebido']:,.2f}"
    )

    col3.metric(
        "Inadimplência com Pix",
        f"{indicadores_pix['Taxa de inadimplência']:.2%}",
        delta=f"{indicadores_pix['Taxa de inadimplência'] - indicadores_atual['Taxa de inadimplência']:.2%}"
    )

    col4.metric(
        "Persistência estimada",
        f"{indicadores_pix['Taxa de persistência']:.2%}",
        delta=f"{indicadores_pix['Taxa de persistência'] - indicadores_atual['Taxa de persistência']:.2%}"
    )

    st.subheader("Comparação dos Cenários")

    comparativo = pd.DataFrame({
        "Indicador": [
            "Prêmio esperado",
            "Prêmio recebido",
            "Prêmio não recebido",
            "Taxa de inadimplência",
            "Atraso médio",
            "Cancelamentos estimados",
            "Taxa de persistência",
            "Valor presente dos recebimentos"
        ],
        "Cenário atual": [
            indicadores_atual["Prêmio esperado"],
            indicadores_atual["Prêmio recebido"],
            indicadores_atual["Prêmio não recebido"],
            indicadores_atual["Taxa de inadimplência"],
            indicadores_atual["Atraso médio"],
            indicadores_atual["Cancelamentos estimados"],
            indicadores_atual["Taxa de persistência"],
            indicadores_atual["Valor presente dos recebimentos"]
        ],
        "Cenário com Pix Automático": [
            indicadores_pix["Prêmio esperado"],
            indicadores_pix["Prêmio recebido"],
            indicadores_pix["Prêmio não recebido"],
            indicadores_pix["Taxa de inadimplência"],
            indicadores_pix["Atraso médio"],
            indicadores_pix["Cancelamentos estimados"],
            indicadores_pix["Taxa de persistência"],
            indicadores_pix["Valor presente dos recebimentos"]
        ]
    })

    st.dataframe(comparativo)

    st.subheader("Fluxo de Caixa Mensal")

    fluxo = fluxo_caixa_mensal(df, df_pix)

    fig_fluxo = px.line(
        fluxo,
        x="Mês",
        y="Receita",
        color="Cenário",
        markers=True,
        title="Fluxo de Caixa Mensal por Cenário"
    )

    st.plotly_chart(fig_fluxo, use_container_width=True)

    st.subheader("Comparação de Prêmio Recebido")

    graf_receita = pd.DataFrame({
        "Cenário": ["Atual", "Com Pix Automático"],
        "Prêmio recebido": [
            indicadores_atual["Prêmio recebido"],
            indicadores_pix["Prêmio recebido"]
        ]
    })

    fig_receita = px.bar(
        graf_receita,
        x="Cenário",
        y="Prêmio recebido",
        title="Prêmio Recebido por Cenário"
    )

    st.plotly_chart(fig_receita, use_container_width=True)

    st.subheader("Análise de Sensibilidade")

    sensibilidade = analise_sensibilidade(
        df,
        taxa_cancelamento,
        taxa_desconto_anual
    )

    st.dataframe(sensibilidade)

    fig_sens = px.line(
        sensibilidade,
        x="Redução da inadimplência",
        y="Ganho financeiro",
        markers=True,
        title="Ganho Financeiro por Nível de Redução da Inadimplência"
    )

    st.plotly_chart(fig_sens, use_container_width=True)

    st.subheader("Base Simulada com Pix Automático")

    st.dataframe(df_pix.head())

    csv_comparativo = comparativo.to_csv(index=False).encode("utf-8")
    csv_sensibilidade = sensibilidade.to_csv(index=False).encode("utf-8")
    csv_base_pix = df_pix.to_csv(index=False).encode("utf-8")

    col_down1, col_down2, col_down3 = st.columns(3)

    col_down1.download_button(
        label="Baixar comparação dos cenários",
        data=csv_comparativo,
        file_name="comparacao_cenarios_pix.csv",
        mime="text/csv"
    )

    col_down2.download_button(
        label="Baixar análise de sensibilidade",
        data=csv_sensibilidade,
        file_name="analise_sensibilidade_pix.csv",
        mime="text/csv"
    )

    col_down3.download_button(
        label="Baixar base simulada com Pix",
        data=csv_base_pix,
        file_name="base_simulada_pix.csv",
        mime="text/csv"
    )