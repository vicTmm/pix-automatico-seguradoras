-- Tabela de apólices
CREATE TABLE apolices (
    id_apolice INTEGER PRIMARY KEY,
    ramo TEXT,
    premio_mensal REAL,
    data_inicio DATE,
    data_fim DATE
);

-- Tabela de segurados
CREATE TABLE segurados (
    id_segurado INTEGER PRIMARY KEY,
    idade INTEGER,
    renda_mensal REAL,
    perfil_pagamento TEXT
);

-- Tabela de pagamentos
CREATE TABLE pagamentos (
    id_pagamento INTEGER PRIMARY KEY,
    id_apolice INTEGER,
    data_vencimento DATE,
    data_pagamento DATE,
    valor_pago REAL,
    status TEXT,
    metodo_pagamento TEXT,
    FOREIGN KEY (id_apolice) REFERENCES apolices(id_apolice)
);