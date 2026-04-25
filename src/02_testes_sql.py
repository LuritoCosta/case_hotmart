import duckdb

fct_purchase_history = '../data/specialized/fct_purchase_history.csv'

query = f"""
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
AND is_gmv_eligible = TRUE
ORDER BY transaction_date;
"""

# Executa a query e transforma o resultado em um DataFrame do Pandas
resultado = duckdb.query(query).df()

print(resultado)