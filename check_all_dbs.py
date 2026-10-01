import sqlite3
import glob
import os
import json

db_files = glob.glob("*.db") + glob.glob("*/*.db")
print("Found DB files:", db_files)

for db_path in db_files:
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        print(f"\n=== DB: {db_path} (tables: {len(tables)}) ===")
        if "master_products" in tables:
            print("FOUND master_products in", db_path)
            cur.execute("SELECT count(*) FROM master_products")
            print("master_products count:", cur.fetchone()[0])
            cur.execute("SELECT name, count(*) FROM master_products GROUP BY name HAVING count(*) > 1")
            dups = cur.fetchall()
            print("Duplicate names:", dups)
            cur.execute("SELECT asin, count(*) FROM master_products WHERE asin IS NOT NULL AND asin != '' GROUP BY asin HAVING count(*) > 1")
            asin_dups = cur.fetchall()
            print("Duplicate ASINs:", asin_dups)
        elif "products" in tables:
            print("FOUND products table in", db_path)
            cur.execute("SELECT count(*) FROM products")
            print("products count:", cur.fetchone()[0])
            cur.execute("SELECT name, count(*) FROM products GROUP BY name HAVING count(*) > 1")
            dups = cur.fetchall()
            print("Duplicate product names:", dups)
    except Exception as e:
        print("Error on", db_path, e)
