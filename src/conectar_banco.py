import sqlite3
import pandas as pd
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT_DIR / "database" / "dados.db"

def conectar_banco():
    return sqlite3.connect(DATABASE_PATH)


def exportar_csv():
    conn = conectar_banco()

    df = pd.read_sql_query("SELECT * FROM pagamentos", conn)

    conn.close()

    df.to_csv(ROOT_DIR / "data" / "pagamentos.csv", index=False)

    print("CSV criado com sucesso em data/pagamentos.csv")


if __name__ == "__main__":
    exportar_csv()
