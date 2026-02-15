"""
Cronos panel API client.
Bearer token + cookies ile _api endpoint'lerine istek atar.
"""
import httpx

BASE_API_URL = "https://cronos.redlanegaming.com/_api"


class CronosAPI:
    def __init__(self, bearer_token: str, cookies: dict | list):
        self.token = bearer_token
        self.cookies = self._normalize_cookies(cookies)
        self.base_url = BASE_API_URL

    @staticmethod
    def _normalize_cookies(cookies) -> dict:
        if isinstance(cookies, dict):
            return cookies
        if isinstance(cookies, list):
            return {c["name"]: c.get("value", "") for c in cookies if c.get("name")}
        return {}

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_pending_withdrawals(self) -> list:
        """
        type=2 (çekim), status=1 (beklemede) ile bekleyen çekimleri döner.
        Bearer token + cookies ile istek atar, JSON parse eder.
        """
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            # Yaygın desen: /financial/transactions veya /withdrawals
            r = await client.get(
                "/financial/transactions",
                params={"type": 2, "status": 1},
                headers=self._headers(),
                cookies=self.cookies,
            )
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("data", data.get("items", data.get("list", [])))
            return []

    async def approve_withdrawal(self, withdrawal_id: str | int) -> dict:
        """Onay endpoint'ine POST atar."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            # Örnek: POST /financial/withdrawal/approve veya /withdrawals/{id}/approve
            r = await client.post(
                "/financial/withdrawal/approve",
                json={"id": withdrawal_id},
                headers=self._headers(),
                cookies=self.cookies,
            )
            r.raise_for_status()
            return r.json() if r.content else {}

    async def reject_withdrawal(self, withdrawal_id: str | int, reason: str) -> dict:
        """Red endpoint'ine POST atar (sebep ile)."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30.0) as client:
            r = await client.post(
                "/financial/withdrawal/reject",
                json={"id": withdrawal_id, "reason": reason},
                headers=self._headers(),
                cookies=self.cookies,
            )
            r.raise_for_status()
            return r.json() if r.content else {}
