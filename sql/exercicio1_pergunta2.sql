-- =============================================================================
-- DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
-- Exercício 1 - Pergunta 2
-- Quais são os 2 produtos que mais faturaram ($) de cada produtor?
-- =============================================================================
-- Regras de negócio: mesmas da Pergunta 1.
--   1. release_date IS NOT NULL (compra paga)
--   2. purchase_status = 'APROVADA' (não cancelada/reembolsada)
--
-- Sem recorte temporal — a pergunta não especifica ano.
--
-- Estratégia em 2 etapas:
--   1) faturamento_por_produto: agrega o GMV por (producer_id, product_id).
--   2) ranqueado: ROW_NUMBER() particionado por produtor, ordenado por
--      faturamento DESC, filtrado <= 2.
--
-- ROW_NUMBER vs RANK:
--   - ROW_NUMBER garante exatamente 2 produtos por produtor mesmo com empate.
--   - Para trazer todos os empatados no 2º lugar, trocar por RANK().
--   - Tiebreaker determinístico em product_id ASC para reprodutibilidade.
-- =============================================================================

WITH faturamento_por_produto AS (
    SELECT
        p.producer_id,
        pi.product_id,
        SUM(pi.purchase_value) AS faturamento
    FROM purchase AS p
    INNER JOIN product_item AS pi
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
            ORDER BY faturamento DESC, product_id
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