"""Database tests: each API action is checked against the rows it should change."""
import os
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from shop.app import create_app
from shop.reset_db import TEST_PASSWORD, reset


def scalar(sql, *params):
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        return conn.execute(sql, params).fetchone()[0]


@pytest.fixture(autouse=True)
def clean_database():
    reset()


@pytest.fixture
def client():
    return create_app().test_client()


def auth(client, username="alice"):
    response = client.post("/api/login", json={"username": username, "password": TEST_PASSWORD})
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_order_decrements_stock_and_writes_one_row(client):
    response = client.post(
        "/api/orders", json={"product_id": 1, "quantity": 3}, headers=auth(client)
    )
    assert response.status_code == 201
    assert scalar("SELECT stock FROM products WHERE id = 1") == 7
    assert scalar("SELECT count(*) FROM orders") == 1
    assert scalar("SELECT total FROM orders") == 7500


def test_rejected_order_changes_nothing(client):
    response = client.post(
        "/api/orders", json={"product_id": 3, "quantity": 1}, headers=auth(client)
    )
    assert response.status_code == 409
    assert scalar("SELECT stock FROM products WHERE id = 3") == 0
    assert scalar("SELECT count(*) FROM orders") == 0


def test_failed_insert_rolls_back_the_stock_update():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            with conn.transaction():
                conn.execute("UPDATE products SET stock = stock - 1 WHERE id = 1")
                conn.execute(
                    "INSERT INTO orders (user_id, product_id, quantity, total) "
                    "VALUES (1, 1, 1, 0)"
                )
    assert scalar("SELECT stock FROM products WHERE id = 1") == 10


def test_database_refuses_negative_stock():
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("UPDATE products SET stock = -1 WHERE id = 1")


def test_password_is_not_stored_in_plain_text():
    stored = scalar("SELECT password_hash FROM users WHERE username = 'alice'")
    assert TEST_PASSWORD not in stored


@pytest.mark.parametrize("quantity", [0, -1, 11, "2", 1.5, True, None])
def test_invalid_quantity_is_rejected_without_a_write(client, quantity):
    response = client.post(
        "/api/orders", json={"product_id": 1, "quantity": quantity}, headers=auth(client)
    )
    assert response.status_code == 400
    assert scalar("SELECT stock FROM products WHERE id = 1") == 10


def test_concurrent_orders_never_oversell(client):
    headers = auth(client)
    app = create_app()

    def buy(_):
        return app.test_client().post(
            "/api/orders", json={"product_id": 1, "quantity": 1}, headers=headers
        ).status_code

    with ThreadPoolExecutor(max_workers=8) as pool:
        statuses = list(pool.map(buy, range(25)))
    assert statuses.count(201) == 10
    assert statuses.count(409) == 15
    assert scalar("SELECT stock FROM products WHERE id = 1") == 0
    assert scalar("SELECT sum(quantity) FROM orders") == 10
