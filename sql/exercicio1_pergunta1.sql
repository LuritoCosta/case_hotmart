-- =============================================================================
-- DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
-- Exercício 1 - Pergunta 1
-- Quais são os 50 maiores produtores em faturamento ($) de 2021?
-- =============================================================================
-- Regras de negócio aplicadas:
--   1. Só há faturamento se a compra foi paga → release_date IS NOT NULL
--   2. GMV exclui canceladas/reembolsadas → purchase_status = 'APROVADA'
--      (status possíveis: INICIADA, APROVADA, CANCELADA, REEMBOLSADA)
--
-- Filtro temporal:
--   release_date — faturamento é reconhecido no dia do pagamento, não do pedido.
--   Uma compra pedida em dez/2020 e paga em jan/2021 entra no faturamento de 2021.
--
-- Join otimizado:
--   prod_item_id + prod_item_partition para permitir partition pruning no lake.
-- =============================================================================

SELECT
    p.producer_id,
    SUM(pi.purchase_value) AS faturamento_2021
FROM purchase AS p
INNER JOIN product_item AS pi
    ON pi.prod_item_id        = p.prod_item_id
    AND pi.prod_item_partition = p.prod_item_partition
WHERE
    p.release_date IS NOT NULL
    AND p.purchase_status = 'APROVADA'
    AND EXTRACT(YEAR FROM p.release_date) = 2021
GROUP BY
    p.producer_id
ORDER BY
    faturamento_2021 DESC
LIMIT 50;