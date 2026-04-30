import sqlite3
import pandas as pd

def conectar_banco():
    return sqlite3.connect("database/dados.db")


def exportar_csv():
    conn = conectar_banco()

    df = pd.read_sql_query("SELECT * FROM pagamentos", conn)

    conn.close()

    df.to_csv("data/pagamentos.csv", index=False)

    print("CSV criado com sucesso em data/pagamentos.csv")


if __name__ == "__main__":
    exportar_csv()