-- =============================================================================
-- DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
-- Exercício 2 - DDL da tabela final
-- =============================================================================
-- Tabela:  analytics.fct_purchase_history
-- Grão:    1 linha por (purchase_id, transaction_date)
-- Objetivo:
--   Snapshot diário, histórico e imutável de cada compra, consolidando as 3
--   fontes de eventos (purchase, product_item, purchase_extra_info).
--   Permite (1) calcular GMV diário por subsidiária, (2) navegar no tempo
--   ("como era o GMV de Jan/23 visto em 31/03/23 vs hoje"), e (3) recuperar
--   facilmente o estado corrente de cada compra via flag is_current.
--
-- Sintaxe: BigQuery / Snowflake-like (ajustar tipos para outros engines).
-- Se o target for Redshift/Postgres, trocar ARRAY<STRING> por TEXT[] e usar
-- a sintaxe de PARTITION equivalente.
-- =============================================================================
 
CREATE TABLE IF NOT EXISTS analytics.fct_purchase_history (
    -- ---- Chaves e partição -------------------------------------------------
    transaction_date      DATE       NOT NULL,   -- dia do evento (D-1) — PARTIÇÃO
    purchase_id           INT64      NOT NULL,   -- chave natural da compra
 
    -- ---- Campos vindos de `purchase` --------------------------------------
    buyer_id              INT64,
    prod_item_id          INT64,
    order_date            DATE,
    release_date          DATE,                  -- NULL = compra não paga
    producer_id           INT64,
    purchase_total_value  NUMERIC(18, 2),        -- valor total declarado na compra
    purchase_status       STRING,                -- INICIADA | APROVADA | CANCELADA | REEMBOLSADA
 
    -- ---- Colunas de partição do lake (lineage / otimização) ---------------
    purchase_partition    INT64,
    prod_item_partition   INT64,
 
    -- ---- Campos vindos de `product_item` ----------------------------------
    product_id            INT64,
    item_quantity         INT64,
    purchase_value        NUMERIC(18, 2),        -- valor do item (usado no GMV)
 
    -- ---- Campo vindo de `purchase_extra_info` -----------------------------
    subsidiary            STRING,                -- 'nacional' | 'internacional'
 
    -- ---- Metadados de rastreabilidade -------------------------------------
    is_current            BOOL       NOT NULL,   -- TRUE = snapshot mais recente da compra
    is_gmv_eligible       BOOL       NOT NULL,   -- TRUE = conta para GMV (paga e aprovada)
    updated_sources       ARRAY<STRING>,         -- ex: ['purchase','product_item']
    etl_loaded_at         TIMESTAMP  NOT NULL    -- quando o ETL escreveu a linha
)
PARTITION BY transaction_date
CLUSTER BY purchase_id
OPTIONS (
    description = "Histórico diário e imutável de compras. 1 linha por (purchase_id, transaction_date). Consolida 3 fontes de evento com forward-fill. Fonte única de verdade para GMV. Coluna is_gmv_eligible pré-calcula a regra de negócio (release_date IS NOT NULL AND purchase_status='APROVADA') para que usuários finais não precisem conhecê-la."
);