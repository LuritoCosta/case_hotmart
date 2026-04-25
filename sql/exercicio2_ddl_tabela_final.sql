-- =============================================================================
-- DESAFIO TÉCNICO HOTMART - ANALYTICS ENGINEER
-- Exercício 2 - DDL da tabela final
-- =============================================================================
-- Tabela:  analytics.fct_purchase_history
-- Grão:    1 linha por (purchase_id, transaction_date)
-- Particionamento:  transaction_date
--
-- Objetivo:
--   Snapshot diário, histórico e imutável de cada compra, consolidando as 3
--   fontes de eventos (purchase, product_item, purchase_extra_info).
--   Permite (1) calcular GMV diário por subsidiária, (2) navegar no tempo
--   ("como era o GMV de Jan/23 visto em 31/03/23"), e (3) recuperar facilmente
--   o estado corrente de cada compra via flag is_current.
-- =============================================================================

CREATE TABLE IF NOT EXISTS analytics.fct_purchase_history (
    -- ---- Chaves e partição -------------------------------------------------
    transaction_date      DATE         NOT NULL,
    purchase_id           BIGINT       NOT NULL,

    -- ---- Campos vindos de `purchase` --------------------------------------
    buyer_id              BIGINT,
    prod_item_id          BIGINT,
    order_date            DATE,
    release_date          DATE,                   
    producer_id           BIGINT,
    purchase_total_value  DECIMAL(18, 2),
    purchase_status       VARCHAR(20),             

    -- ---- Colunas de partição do lake (lineage / otimização) ---------------
    purchase_partition    BIGINT,
    prod_item_partition   BIGINT,

    -- ---- Campos vindos de `product_item` ----------------------------------
    product_id            BIGINT,
    purchase_value        DECIMAL(18, 2),

    -- ---- Campo vindo de `purchase_extra_info` -----------------------------
    subsidiary            VARCHAR(20),             

    -- ---- Metadados de rastreabilidade -------------------------------------
    is_current            BOOLEAN      NOT NULL,    -- TRUE = snapshot mais recente
    is_gmv_eligible       BOOLEAN      NOT NULL,    -- TRUE = conta para GMV (paga e aprovada)
    updated_sources       VARCHAR(100),             -- ex: 'purchase,product_item'
    etl_loaded_at         TIMESTAMP    NOT NULL,    -- timestamp da carga

    PRIMARY KEY (purchase_id, transaction_date)
);

CREATE INDEX IF NOT EXISTS idx_fct_is_current
    ON analytics.fct_purchase_history (is_current)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_fct_order_date
    ON analytics.fct_purchase_history (order_date);

CREATE INDEX IF NOT EXISTS idx_fct_release_date
    ON analytics.fct_purchase_history (release_date);