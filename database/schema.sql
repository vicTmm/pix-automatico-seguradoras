-- Tabela de segurados
CREATE TABLE segurados (
    id_segurado INTEGER PRIMARY KEY,
    idade INTEGER,
    renda_mensal REAL,
    perfil_pagamento TEXT
);

-- Tabela de apolices
CREATE TABLE apolices (
    id_apolice INTEGER PRIMARY KEY,
    id_segurado INTEGER,
    ramo TEXT,
    premio_mensal REAL,
    data_inicio DATE,
    data_fim DATE,
    FOREIGN KEY (id_segurado) REFERENCES segurados(id_segurado)
);

-- Tabela de pagamentos / parcelas
CREATE TABLE pagamentos (
    id_pagamento INTEGER PRIMARY KEY,
    id_apolice INTEGER,
    id_segurado INTEGER,
    id_parcela INTEGER,
    competencia TEXT,
    ramo TEXT,
    perfil_pagamento TEXT,
    data_vencimento DATE,
    data_pagamento DATE,
    valor_esperado REAL,
    valor_pago REAL,
    status TEXT,
    metodo_pagamento TEXT,
    FOREIGN KEY (id_apolice) REFERENCES apolices(id_apolice),
    FOREIGN KEY (id_segurado) REFERENCES segurados(id_segurado)
);
