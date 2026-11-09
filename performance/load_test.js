// Load test for the local system under test. Never point this at a site you do not own.
import { check, sleep } from 'k6';
import http from 'k6/http';
import { Counter } from 'k6/metrics';

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const ordersCreated = new Counter('orders_created');

// A sold-out answer is correct behaviour here, so it must not count as a failed request.
http.setResponseCallback(http.expectedStatuses(200, 201, 409));

export const options = {
  scenarios: {
    browse: { executor: 'constant-vus', vus: 15, duration: '30s', exec: 'browse' },
    buy: { executor: 'constant-vus', vus: 10, duration: '30s', exec: 'buy' },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<800'],
    checks: ['rate>0.99'],
  },
};

export function setup() {
  const response = http.post(
    `${BASE}/api/login`,
    JSON.stringify({ username: 'alice', password: 'test-only-password' }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(response, { 'login succeeded': (r) => r.status === 200 });
  return { token: response.json('token') };
}

export function browse() {
  const response = http.get(`${BASE}/api/products`);
  check(response, { 'products returned': (r) => r.status === 200 && r.json().length === 3 });
  sleep(0.2);
}

export function buy(data) {
  const response = http.post(
    `${BASE}/api/orders`,
    JSON.stringify({ product_id: 2, quantity: 1 }),
    { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${data.token}` } },
  );
  check(response, { 'order accepted or sold out': (r) => r.status === 201 || r.status === 409 });
  if (response.status === 201) ordersCreated.add(1);
  sleep(0.2);
}
