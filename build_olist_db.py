"""Olist CSV 파일들을 SQLite DB(olist.db) 하나로 합칩니다.

사용법:
  1) Olist CSV 8개를 data 폴더에 넣기
  2) python build_olist_db.py
"""
import os
import sqlite3

import pandas as pd

DATA_DIR = "data"
DB_PATH = "olist.db"

# CSV 파일 → 테이블 이름
TABLES = {
    "olist_customers_dataset.csv": "customers",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "product_category_name_translation.csv": "category_translation",
}

# 자주 JOIN하는 열에 인덱스를 만들어 쿼리를 빠르게
INDEXES = [
    ("orders", "order_id"), ("orders", "customer_id"),
    ("customers", "customer_id"), ("customers", "customer_unique_id"),
    ("order_items", "order_id"), ("order_items", "product_id"), ("order_items", "seller_id"),
    ("order_payments", "order_id"), ("order_reviews", "order_id"),
    ("products", "product_id"), ("sellers", "seller_id"),
    ("category_translation", "product_category_name"),
]


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)

    for csv_name, table in TABLES.items():
        path = os.path.join(DATA_DIR, csv_name)
        df = pd.read_csv(path)
        df.to_sql(table, conn, index=False)
        print(f"{table:<22} {len(df):>8,}행")

    for table, col in INDEXES:
        conn.execute(f"CREATE INDEX idx_{table}_{col} ON {table}({col})")

    conn.commit()
    conn.execute("VACUUM")
    conn.close()
    print(f"\n완료: {DB_PATH} ({os.path.getsize(DB_PATH) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
