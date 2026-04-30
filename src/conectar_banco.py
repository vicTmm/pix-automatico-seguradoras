import sqlite3


def conectar_banco():
    conn = sqlite3.connect("database/dados.db")
    return conn