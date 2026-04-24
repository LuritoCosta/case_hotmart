import duckdb

# -- =============================================================================
# -- PERGUNTA 2: Quais são os 2 produtos que mais faturaram ($) de cada produtor?
# -- =============================================================================
# -- Estratégia em 2 etapas com CTEs:
# --   1) faturamento_por_produto: agrega o GMV por (producer_id, product_id).
# --      Relação produtor ↔ produto existe via prod_item_id.
# --   2) ranqueado: ROW_NUMBER() particionado por produtor, ordenado por
# --      faturamento desc, filtrado <= 2.
# --
# -- Observações:
# --   - ROW_NUMBER garante exatamente 2 produtos por produtor mesmo com empate.
# --     Para trazer todos os empatados no 2º lugar, trocar por RANK().
# --   - Sem recorte temporal (a pergunta não especifica ano).
# -- =============================================================================

purchase_current = '../data/raw/purchase_current.csv'
product_item_current = '../data/raw/product_item_current.csv'

query = f"""
    WITH faturamento_por_produto AS (
        SELECT
            p.producer_id,
            pi.product_id,
            SUM(pi.item_quantity * pi.purchase_value) AS faturamento
        FROM '{purchase_current}' AS p
        INNER JOIN '{product_item_current}' AS pi
            ON pi.prod_item_id        = p.prod_item_id
            AND pi.prod_item_partition = p.prod_item_partition
        WHERE
            p.release_date IS NOT NULL
            AND p.purchase_status = 'APROVADA'
        GROUP BY
            p.producer_id,
            pi.product_id
    ),
    
    ranqueado AS (
        SELECT
            producer_id,
            product_id,
            faturamento,
            ROW_NUMBER() OVER (
                PARTITION BY producer_id
                ORDER BY faturamento DESC, product_id        -- tiebreaker determinístico
            ) AS rn
        FROM faturamento_por_produto
    )
    
    SELECT
        producer_id,
        product_id,
        faturamento
    FROM ranqueado
    WHERE rn <= 2
    ORDER BY
        producer_id,
        faturamento DESC;
"""

# Executa a query e transforma o resultado em um DataFrame do Pandas
resultado = duckdb.query(query).df()

print(resultado)