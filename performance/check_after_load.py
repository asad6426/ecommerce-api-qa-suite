"""After the load test, the database must agree with what the API told its clients."""
import json
import os
import sys

import psycopg

STARTING_STOCK = 50

with open(sys.argv[1], encoding="utf-8") as handle:
    created = json.load(handle)["metrics"]["orders_created"]["count"]

with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
    stock = conn.execute("SELECT stock FROM products WHERE id = 2").fetchone()[0]
    sold, rows = conn.execute(
        "SELECT coalesce(sum(quantity), 0), count(*) FROM orders WHERE product_id = 2"
    ).fetchone()

print(f"orders the API confirmed: {created}")
print(f"orders in the database:   {rows}")
print(f"units sold:               {sold}")
print(f"stock remaining:          {stock}")

assert created == rows, "API and database disagree on the number of orders"
assert sold + stock == STARTING_STOCK, "Units sold and stock do not add up"
assert stock >= 0, "Stock went negative"
print("NO OVERSELLING: database and API agree")
