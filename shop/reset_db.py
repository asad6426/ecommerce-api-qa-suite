"""Rebuild the database with known test data. Run: python -m shop.reset_db"""
import os
from pathlib import Path

import psycopg
from werkzeug.security import generate_password_hash

TEST_PASSWORD = "test-only-password"
PRODUCTS = [("Keyboard", 2500, 10), ("Limited Mouse", 1200, 50), ("Sold Out Cable", 300, 0)]


def reset():
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    password_hash = generate_password_hash(TEST_PASSWORD, method="pbkdf2:sha256:1000")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute(schema)
        for username in ("alice", "bob"):
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                (username, password_hash),
            )
        for row in PRODUCTS:
            conn.execute("INSERT INTO products (name, price, stock) VALUES (%s, %s, %s)", row)


if __name__ == "__main__":
    reset()
