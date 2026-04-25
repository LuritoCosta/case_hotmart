import pandas as pd

# =============================================================================
# TABELAS DE EVENTOS (Exercício 2) - dados exatos do PDF
# =============================================================================
 
purchase_events = pd.DataFrame([
    # td_dt,                td,           pid,buyer, prod_it, order_dt,    release_dt,  producer, p_total, status,    p_part, pi_part
    ('2023-01-20 22:00:00','2023-01-20', 55, 15947, 5,       '2023-01-20','2023-01-20', 852852,  500.00, 'APROVADA',  5,      5),
    ('2023-01-26 00:01:00','2023-01-26', 56, 369798,746520,  '2023-01-25', None,        963963, 2400.00, 'INICIADA',  6,      0),
    ('2023-02-05 10:00:00','2023-02-05', 55, 160001,5,       '2023-01-20','2023-01-20', 852852,  500.00, 'APROVADA',  5,      5),
    ('2023-02-26 03:00:00','2023-02-26', 69, 160001,18,      '2023-02-26','2023-02-28', 96967,  4000.00, 'APROVADA',  7,      8),
    ('2023-07-15 09:00:00','2023-07-15', 55, 160001,5,       '2023-01-20','2023-03-01', 852852,  550.00, 'APROVADA',  5,      5),
], columns=['transaction_datetime','transaction_date','purchase_id','buyer_id',
            'prod_item_id','order_date','release_date','producer_id',
            'purchase_total_value','purchase_status','purchase_partition','prod_item_partition'])
 
product_item_events = pd.DataFrame([
    ('2023-01-20 22:02:00','2023-01-20', 55, 696969, 10,    50.00),
    ('2023-01-25 23:59:59','2023-01-25', 56, 808080, 120, 2400.00),
    ('2023-02-26 03:00:00','2023-02-26', 69, 373737, 2,  2000.00),
    ('2023-07-12 09:00:00','2023-07-12', 55, 696969, 10,    55.00),
], columns=['transaction_datetime','transaction_date','purchase_id','product_id',
            'item_quantity','purchase_value'])
 
extra_info_events = pd.DataFrame([
    ('2023-01-23 00:05:00','2023-01-23', 55, 'nacional'),
    ('2023-01-25 23:59:59','2023-01-25', 56, 'internacional'),
    ('2023-02-28 01:10:00','2023-02-28', 69, 'nacional'),
    ('2023-03-12 07:00:00','2023-03-12', 69, 'internacional'),
], columns=['transaction_datetime','transaction_date','purchase_id','subsidiary'])


purchase_current = pd.DataFrame([
    (55, 15947, 5, '2022-12-01', '2022-12-01', 852852, 5, 5,'APROVADA'),
    (56, 369798, 746520, '2022-12-25', '2022-12-25', 963963, 6, 0,'APROVADA'),
    (57, 147, 98736, '2021-07-03', '2021-07-03', 963963, 7, 6,'APROVADA'),
    (58, 986533, 6565, '2021-10-12', None, 200478, 8, 5,'INICIADA'),
], columns=['purchase_id', 'buyer_id', 'prod_item_id', 'order_date', 'release_date', 
            'producer_id', 'purchase_partition', 'prod_item_partition','purchase_status'])

product_item_current = pd.DataFrame([
    (1, 69, 5, 500.00, 5),
    (5, 69, 120, 1.00, 0),
    (98736, 37, 69, 25.00, 6),
    (3, 96, 369, 140.00, 5),
], columns=['prod_item_id', 'product_id', 'item_quantity', 'purchase_value', 'prod_item_partition'])


# =============================================================================
# EXPORTANDO PARA CSV
# =============================================================================

purchase_events.to_csv(fr'../data/raw/purchase_events.csv', index=False)
product_item_events.to_csv(fr'../data/raw/product_item_events.csv', index=False)
extra_info_events.to_csv(fr'../data/raw/extra_info_events.csv', index=False)
purchase_current.to_csv(fr'../data/raw/purchase_current.csv', index=False)
product_item_current.to_csv(fr'../data/raw/product_item_current.csv', index=False)