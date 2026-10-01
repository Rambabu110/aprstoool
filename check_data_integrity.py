import sqlite3
import json

db_path = r"d:\tools\APRS\data\research_engine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

report = {}

# 1. Products total count
cursor.execute("SELECT COUNT(*) FROM master_products")
report["master_products_count"] = cursor.fetchone()[0]

# 2. Duplicate titles/names in master_products
cursor.execute("SELECT name, COUNT(*) as cnt FROM master_products GROUP BY name HAVING cnt > 1")
report["duplicate_names"] = [dict(r) for r in cursor.fetchall()]

# 3. Duplicate product_id in master_products
cursor.execute("SELECT product_id, COUNT(*) as cnt FROM master_products GROUP BY product_id HAVING cnt > 1")
report["duplicate_product_ids"] = [dict(r) for r in cursor.fetchall()]

# 4. Intelligence table check
try:
    cursor.execute("SELECT COUNT(*) FROM product_intelligence")
    report["product_intelligence_count"] = cursor.fetchone()[0]
    cursor.execute("SELECT product_id, COUNT(*) as cnt FROM product_intelligence GROUP BY product_id HAVING cnt > 1")
    report["duplicate_intelligence"] = [dict(r) for r in cursor.fetchall()]
except Exception as e:
    report["product_intelligence_error"] = str(e)

# 5. Evidence table check
try:
    cursor.execute("SELECT COUNT(*) FROM intelligence_evidence")
    report["intelligence_evidence_count"] = cursor.fetchone()[0]
    cursor.execute("SELECT product_id, signal_type, source, COUNT(*) as cnt FROM intelligence_evidence GROUP BY product_id, signal_type, source HAVING cnt > 1")
    report["duplicate_evidence"] = [dict(r) for r in cursor.fetchall()]
except Exception as e:
    report["intelligence_evidence_error"] = str(e)

# 6. Orphaned records
orphans = {}
try:
    cursor.execute("""
        SELECT COUNT(*) FROM product_intelligence 
        WHERE product_id NOT IN (SELECT product_id FROM master_products)
    """)
    orphans["product_intelligence_orphans"] = cursor.fetchone()[0]
except Exception as e:
    orphans["product_intelligence_orphans_err"] = str(e)

try:
    cursor.execute("""
        SELECT COUNT(*) FROM multi_platform_listings 
        WHERE product_id NOT IN (SELECT product_id FROM master_products)
    """)
    orphans["multi_platform_orphans"] = cursor.fetchone()[0]
except Exception as e:
    orphans["multi_platform_orphans_err"] = str(e)

try:
    cursor.execute("""
        SELECT COUNT(*) FROM intelligence_evidence 
        WHERE product_id NOT IN (SELECT product_id FROM master_products)
    """)
    orphans["intelligence_evidence_orphans"] = cursor.fetchone()[0]
except Exception as e:
    orphans["intelligence_evidence_orphans_err"] = str(e)

report["orphans"] = orphans

# 7. Unexpected NULLs in critical columns
null_checks = {}
cursor.execute("SELECT COUNT(*) FROM master_products WHERE name IS NULL OR name = ''")
null_checks["products_null_name"] = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM master_products WHERE planned_msrp IS NULL")
null_checks["products_null_planned_msrp"] = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM master_products WHERE status IS NULL")
null_checks["products_null_status"] = cursor.fetchone()[0]
report["null_checks"] = null_checks

# 8. All tables list with row counts
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
tables = [r[0] for r in cursor.fetchall()]
table_counts = {}
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM `{t}`")
    table_counts[t] = cursor.fetchone()[0]
report["table_counts"] = table_counts

with open(r"d:\tools\APRS\data_integrity_result.json", "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print("Data integrity check completed successfully. Wrote to data_integrity_result.json")
