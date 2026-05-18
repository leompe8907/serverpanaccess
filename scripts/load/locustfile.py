"""
Pruebas de carga básicas (Fase 3).

Uso:
  pip install locust
  locust -f scripts/load/locustfile.py --host http://127.0.0.1:8000

Variables:
  LOCUST_USERNAME / LOCUST_PASSWORD — credenciales portal PanAccess
"""
import os

from locust import HttpUser, between, task


class PortalUser(HttpUser):
    wait_time = between(1, 3)
    token = None

    def on_start(self):
        username = os.getenv("LOCUST_USERNAME", "")
        password = os.getenv("LOCUST_PASSWORD", "")
        if not username or not password:
            return
        res = self.client.post(
            "/api/auth/login/",
            json={"username": username, "password": password},
            name="auth-login",
        )
        if res.ok:
            data = res.json()
            self.token = data.get("access") or data.get("access_token")

    def _auth_headers(self):
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    @task(3)
    def profile_me(self):
        if not self.token:
            return
        self.client.get(
            "/api/v1/profile/me/",
            headers=self._auth_headers(),
            name="profile-me",
        )

    @task(2)
    def profile_products(self):
        if not self.token:
            return
        self.client.get(
            "/api/v1/profile/products/",
            headers=self._auth_headers(),
            name="profile-products",
        )

    @task(1)
    def health(self):
        self.client.get("/ready/", name="ready")
