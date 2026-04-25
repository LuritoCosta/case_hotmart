import duckdb

# -- Exercício 1 - SQL
# -- =============================================================================
# -- Regras de negócio de faturamento (do vídeo da Catarina + diagrama):
# --   1. Só há faturamento se a compra foi paga → release_date IS NOT NULL
# --   2. GMV exclui canceladas/reembolsadas → purchase_status = 'APROVADA'
# --      (o diagrama define 4 status: INICIADA, APROVADA, CANCELADA, REEMBOLSADA;
# --       só APROVADA configura faturamento)
# --
# -- Join otimizado: uso tanto `prod_item_id` quanto `prod_item_partition` para
# -- aproveitar o particionamento do lake (pruning de partição no product_item).
# -- =============================================================================

# -- =============================================================================
# -- PERGUNTA 1: Quais são os 50 maiores produtores em faturamento ($) de 2021?
# -- =============================================================================
# -- Filtro temporal por release_date: o faturamento é reconhecido quando o
# -- pagamento é efetuado. Uma compra pedida em dez/2020 mas paga em jan/2021
# -- compõe o faturamento de 2021 (alinha com a ótica contábil/financeira).
# -- =============================================================================

purchase_current = '../data/raw/purchase_current.csv'
product_item_current = '../data/raw/product_item_current.csv'

query = f"""
    SELECT
        p.producer_id,
        SUM(pi.purchase_value) AS faturamento_2021
    FROM '{purchase_current}' AS p
    INNER JOIN '{product_item_current}' AS pi
        ON pi.prod_item_id        = p.prod_item_id
        AND pi.prod_item_partition = p.prod_item_partition    -- pruning de partição
    WHERE
        p.release_date IS NOT NULL                           -- foi paga
        AND p.purchase_status = 'APROVADA'                   -- não foi cancelada/reembolsada
        AND EXTRACT(YEAR FROM p.release_date) = 2021         -- faturamento de 2021
    GROUP BY
        p.producer_id
    ORDER BY
        faturamento_2021 DESC
    LIMIT 50;
"""

# Executa a query e transforma o resultado em um DataFrame do Pandas
resultado = duckdb.query(query).df()

print(resultado)