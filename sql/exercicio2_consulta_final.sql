-- =============================================================================
-- CONSULTA PRINCIPAL (entregável): GMV DIÁRIO POR SUBSIDIÁRIA — dados correntes
-- =============================================================================
-- Visão "estado do mundo hoje". Usa apenas os snapshots is_current=TRUE.
 
SELECT
    order_date          AS data_compra,
    subsidiary          AS subsidiaria,
    SUM(purchase_value) AS gmv
FROM analytics.fct_purchase_history
WHERE
    is_current      = TRUE
    AND is_gmv_eligible = TRUE     -- regra de GMV (paga + aprovada) encapsulada
GROUP BY
    order_date,
    subsidiary
ORDER BY
    data_compra,
    subsidiaria;
 
 
-- =============================================================================
-- CONSULTA DE NAVEGAÇÃO NO TEMPO: GMV visto em uma data passada
-- =============================================================================
-- Atende ao requisito: "uma consulta com cutoff fixo é 100% reprodutível".
-- Para cada purchase_id, pega a versão cujo transaction_date é o MAIOR <=
-- data de corte ("como a compra estava sendo vista naquele dia").
-- Depois aplica a mesma regra de GMV.
--
-- Troque :cutoff_date pelo parâmetro do seu engine (ex: '2023-03-31').
 
WITH snapshot_em_cutoff AS (
    SELECT
        purchase_id,
        order_date,
        release_date,
        purchase_status,
        subsidiary,
        purchase_value,
        ROW_NUMBER() OVER (
            PARTITION BY purchase_id
            ORDER BY transaction_date DESC
        ) AS rn
    FROM analytics.fct_purchase_history
    WHERE transaction_date <= DATE(:cutoff_date)
)
 
SELECT
    order_date          AS data_compra,
    subsidiary          AS subsidiaria,
    SUM(purchase_value) AS gmv
FROM snapshot_em_cutoff
WHERE
    rn = 1
    AND release_date IS NOT NULL
    AND purchase_status = 'APROVADA'
    AND order_date BETWEEN DATE('2023-01-01') AND DATE('2023-01-31')
GROUP BY
    order_date,
    subsidiary
ORDER BY
    data_compra,
    subsidiaria;
 
 
-- =============================================================================
-- CONSULTA DE AUDITORIA: histórico de alterações de uma compra específica
-- =============================================================================
-- Útil para o time financeiro/auditoria investigar "o que mudou e quando"
-- numa compra específica. Cada linha = uma versão no tempo.
 
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
FROM analytics.fct_purchase_history
WHERE purchase_id = 55
ORDER BY transaction_date;