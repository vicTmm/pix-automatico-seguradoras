import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Simulador Pix Automático", layout="wide")

st.title("Simulador Atuarial do Pix Automático")
st.write("Importe uma base de pagamentos para simular o impacto do Pix Automático.")

uploaded_file = st.file_uploader("Importe um arquivo CSV ou Excel", type=["csv", "xlsx"])

if uploaded_file is not None:
    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    st.subheader("Prévia da base")
    st.dataframe(df.head())

    st.write("Colunas encontradas:")
    st.write(list(df.columns))

    colunas_necessarias = ["id_apolice", "data_vencimento", "data_pagamento", "valor_pago", "status", "metodo_pagamento"]
    faltantes = [c for c in colunas_necessarias if c not in df.columns]

    if faltantes:
        st.error(f"Colunas faltantes: {faltantes}")
        st.stop()

    reducao = st.slider("Redução esperada da inadimplência", 0, 100, 40, 5) / 100

    df_pix = df.copy()
    inadimplentes = df_pix["status"] == "Inadimplente"
    n_recuperados = int(inadimplentes.sum() * reducao)

    if n_recuperados > 0:
        indices = df_pix[inadimplentes].sample(n=n_recuperados, random_state=42).index
        premio_medio = df[df["valor_pago"] > 0]["valor_pago"].mean()

        df_pix.loc[indices, "status"] = "Pago"
        df_pix.loc[indices, "valor_pago"] = premio_medio
        df_pix.loc[indices, "metodo_pagamento"] = "Pix Automático"

    receita_atual = df["valor_pago"].sum()
    receita_pix = df_pix["valor_pago"].sum()

    inad_atual = (df["status"] == "Inadimplente").mean()
    inad_pix = (df_pix["status"] == "Inadimplente").mean()

    col1, col2, col3 = st.columns(3)

    col1.metric("Receita atual", f"R$ {receita_atual:,.2f}")
    col2.metric("Receita com Pix", f"R$ {receita_pix:,.2f}", f"R$ {receita_pix - receita_atual:,.2f}")
    col3.metric("Inadimplência com Pix", f"{inad_pix:.2%}", f"{inad_pix - inad_atual:.2%}")

    comparativo = pd.DataFrame({
        "Cenário": ["Atual", "Com Pix Automático"],
        "Receita": [receita_atual, receita_pix],
        "Inadimplência": [inad_atual, inad_pix]
    })

    st.subheader("Comparativo")
    st.dataframe(comparativo)

    st.plotly_chart(px.bar(comparativo, x="Cenário", y="Receita", title="Comparação de Receita"), use_container_width=True)
    st.plotly_chart(px.bar(comparativo, x="Cenário", y="Inadimplência", title="Comparação de Inadimplência"), use_container_width=True)

else:
    st.info("Aguardando upload da base.")