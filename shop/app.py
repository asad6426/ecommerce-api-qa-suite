"""A small shop API used as the system under test. All data is made up."""
import os
import secrets
from functools import wraps

import psycopg
from flask import Flask, g, jsonify, request
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash

MAX_QUANTITY = 10


def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def error(status, message):
    return jsonify(error=message), status


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error(401, "Authentication required")
        with connect() as conn:
            row = conn.execute(
                "SELECT user_id FROM tokens WHERE token = %s", (header[7:],)
            ).fetchone()
        if row is None:
            return error(401, "Invalid token")
        g.user_id = row["user_id"]
        return view(*args, **kwargs)

    return wrapper


def valid_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def create_app():
    app = Flask(__name__)

    @app.get("/api/health")
    def health():
        with connect() as conn:
            conn.execute("SELECT 1")
        return jsonify(status="ok")

    @app.post("/api/login")
    def login():
        body = request.get_json(silent=True) or {}
        with connect() as conn:
            user = conn.execute(
                "SELECT id, password_hash FROM users WHERE username = %s",
                (body.get("username"),),
            ).fetchone()
            password = body.get("password")
            if (
                user is None
                or not isinstance(password, str)
                or not check_password_hash(user["password_hash"], password)
            ):
                return error(401, "Invalid username or password")
            token = secrets.token_urlsafe(32)
            conn.execute(
                "INSERT INTO tokens (token, user_id) VALUES (%s, %s)", (token, user["id"])
            )
        return jsonify(token=token)

    @app.get("/api/products")
    def products():
        with connect() as conn:
            rows = conn.execute("SELECT id, name, price, stock FROM products ORDER BY id").fetchall()
        return jsonify(rows)

    @app.get("/api/products/<int:product_id>")
    def product(product_id):
        with connect() as conn:
            row = conn.execute(
                "SELECT id, name, price, stock FROM products WHERE id = %s", (product_id,)
            ).fetchone()
        return jsonify(row) if row else error(404, "Product not found")

    @app.post("/api/orders")
    @login_required
    def create_order():
        body = request.get_json(silent=True) or {}
        product_id, quantity = body.get("product_id"), body.get("quantity")
        if not valid_int(product_id):
            return error(400, "product_id must be an integer")
        if not valid_int(quantity) or not 1 <= quantity <= MAX_QUANTITY:
            return error(400, f"quantity must be between 1 and {MAX_QUANTITY}")
        with connect() as conn, conn.transaction():
            # The row lock makes concurrent buyers of the same product wait their turn.
            item = conn.execute(
                "SELECT price, stock FROM products WHERE id = %s FOR UPDATE", (product_id,)
            ).fetchone()
            if item is None:
                return error(404, "Product not found")
            if item["stock"] < quantity:
                return error(409, "Insufficient stock")
            remaining = item["stock"] - quantity
            conn.execute("UPDATE products SET stock = %s WHERE id = %s", (remaining, product_id))
            total = item["price"] * quantity
            order = conn.execute(
                "INSERT INTO orders (user_id, product_id, quantity, total) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (g.user_id, product_id, quantity, total),
            ).fetchone()
        return jsonify(id=order["id"], total=total, stock_after=remaining), 201

    @app.get("/api/orders/<int:order_id>")
    @login_required
    def get_order(order_id):
        with connect() as conn:
            order = conn.execute(
                "SELECT id, user_id, product_id, quantity, total FROM orders WHERE id = %s",
                (order_id,),
            ).fetchone()
        if order is None:
            return error(404, "Order not found")
        if order["user_id"] != g.user_id:
            return error(403, "This order belongs to another customer")
        return jsonify(order)

    return app


app = create_app()
