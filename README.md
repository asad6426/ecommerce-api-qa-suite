# E-commerce API QA Suite

[![API QA](https://github.com/asad6426/ecommerce-api-qa-suite/actions/workflows/qa.yml/badge.svg)](https://github.com/asad6426/ecommerce-api-qa-suite/actions/workflows/qa.yml)

API, database and load testing for a small online shop API. The API exists only as a system under test, so every test runs against my own service and all data is made up.

## What is tested

| Layer | Tool | Coverage |
| --- | --- | --- |
| API | Postman, run with Newman | Login, products, orders, validation, authorization ([collection](postman/shop-api.postman_collection.json)) |
| Database | Pytest and PostgreSQL | Rows changed by each action, transactions, constraints, concurrency ([tests](tests/test_database.py)) |
| Performance | k6 | Browsing and buying at the same time ([script](performance/load_test.js)) |
| Data integrity | Python and SQL | The database must match what the API confirmed during load ([check](performance/check_after_load.py)) |

All 22 test cases are listed with expected results in [`docs/test-cases.csv`](docs/test-cases.csv).

## Results

From the latest GitHub Actions run against PostgreSQL 16:

| Check | Result |
| --- | --- |
| Postman | 14 requests, 25 assertions, 0 failed |
| Pytest database tests | 13 passed |
| k6 load | 25 virtual users for 30 seconds, 2,785 requests |
| Response time | p95 109 ms, average 69 ms |
| Failed requests | 0% (a sold-out answer counts as correct behaviour) |
| Overselling check | 50 orders confirmed, 50 rows, 0 stock left |

The overselling check is the most useful result. Ten virtual users compete for 50 units, and a row lock in the order transaction means exactly 50 orders succeed.

## Examples of what the tests catch

- A customer reading another customer's order must get 403 and no order data.
- A quantity of 0, -1, 11, text, a decimal, `true` or `null` must be rejected with nothing written.
- A failed insert must roll back the stock change made in the same transaction.
- With 25 simultaneous buyers for 10 units, exactly 10 succeed and 15 are told it is sold out.

## Limits

- The load test runs on one GitHub Actions runner with the API and database on the same machine, so the timings are a baseline for this setup and do not predict production capacity.
- It is a short load test. There are no soak, stress or spike scenarios.
- This suite covers the API only. There is no browser testing here.

## Run it

You need PostgreSQL, Node.js and [k6](https://k6.io/). Run these from the repository root:

```bash
pip install -r requirements.txt
npm install -g newman
export DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/shop

python -m pytest -q

python -m shop.reset_db
gunicorn shop.app:app --bind 127.0.0.1:8000 --workers 4 &
newman run postman/shop-api.postman_collection.json -e postman/local.postman_environment.json

python -m shop.reset_db
k6 run --summary-export=k6-summary.json performance/load_test.js
python performance/check_after_load.py k6-summary.json
```

The collection and environment can also be imported into the Postman app.

Built with Claude Code.
