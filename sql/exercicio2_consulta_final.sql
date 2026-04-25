-- =============================================================================
-- DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
-- Exercício 2 - Consulta final + validações da tabela
-- =============================================================================
-- A coluna `is_gmv_eligible` encapsula a regra de negócio de GMV:
--    release_date IS NOT NULL AND purchase_status = 'APROVADA'
-- O usuário final não precisa conhecer a regra — só filtra is_gmv_eligible.
-- =============================================================================


-- =============================================================================
-- 1. CONSULTA PRINCIPAL (entregável): GMV DIÁRIO POR SUBSIDIÁRIA — CORRENTE
-- =============================================================================
SELECT
    release_date                                AS data_compra,
    subsidiary                                  AS subsidiaria,
    SUM(purchase_value)                         AS gmv
FROM '{fct_purchase_history}'
WHERE
    is_current      = TRUE
    AND is_gmv_eligible = TRUE
GROUP BY
    release_date,
    subsidiary
ORDER BY
    data_compra,
    subsidiaria;


-- =============================================================================
-- 2. NAVEGAÇÃO NO TEMPO — GMV de Jan/2023 visto em uma data passada (cutoff)
-- =============================================================================
-- Para cada purchase_id, pega a versão cujo transaction_date é o MAIOR <= cutoff.
-- "Como a base estava sendo vista na data do cutoff".
-- Trocar a data do cutoff conforme necessário.

WITH snapshot_em_cutoff AS (
    SELECT
        purchase_id,
        order_date,
        release_date,
        purchase_status,
        subsidiary,
        purchase_value,
        is_gmv_eligible,
        is_current,
        ROW_NUMBER() OVER (
            PARTITION BY purchase_id
            ORDER BY transaction_date DESC
        ) AS rn
    FROM '{fct_purchase_history}'
    WHERE transaction_date <= DATE '2023-03-01'
)

SELECT
    order_date                          AS data_compra,
    purchase_id                         AS id_compra,
    subsidiary                          AS subsidiaria,
    SUM(purchase_value)                 AS gmv
FROM snapshot_em_cutoff
WHERE
    rn = 1
    AND is_gmv_eligible = TRUE        
GROUP BY
    order_date,
    purchase_id,
    subsidiary
ORDER BY
    data_compra,
    id_compra,
    subsidiaria;


-- =============================================================================
-- 3. AUDITORIA — histórico completo de uma compra
-- =============================================================================
-- "O que mudou na compra X e quando?" — cada linha = uma versão no tempo.

SELECT
    transaction_date,
    purchase_id,
    release_date,
    purchase_status,
    purchase_value,
    subsidiary,
    is_gmv_eligible,
    updated_sources,
    is_current
FROM '{fct_purchase_history}'
WHERE purchase_id = 55
ORDER BY transaction_date;