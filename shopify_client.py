"""Shopify Admin REST API client with pagination, rate limiting, and retries."""

from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Iterator

import requests

from config import ShopifyConfig
from shopify_auth import resolve_access_token

logger = logging.getLogger(__name__)

RATE_LIMIT_STATUS = 429
SHOPIFY_PAGE_LIMIT = 250


class ShopifyAPIError(Exception):
    """Raised when Shopify returns a non-recoverable error."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        self._min_interval = 1.0 / max(requests_per_second, 0.1)
        self._lock = threading.Lock()
        self._last_request = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


def _parse_link_header(link_header: str | None) -> dict[str, str]:
    if not link_header:
        return {}
    links: dict[str, str] = {}
    for part in link_header.split(","):
        section = part.strip().split(";")
        if len(section) < 2:
            continue
        url = section[0].strip("<>")
        rel_match = re.search(r'rel="([^"]+)"', section[1])
        if rel_match:
            links[rel_match.group(1)] = url
    return links


class ShopifyClient:
    def __init__(self, config: ShopifyConfig) -> None:
        self._config = config
        access_token = resolve_access_token(config)
        self._session = requests.Session()
        self._session.headers.update(
            {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )
        self._rate_limiter = RateLimiter(config.requests_per_second)
        self._product_cache: dict[int, dict[str, Any]] = {}
        self._location_cache: dict[int, dict[str, Any]] = {}

    def _wait_retry(self, attempt: int) -> float:
        base = self._config.min_wait_seconds * (
            self._config.backoff_multiplier ** max(attempt - 1, 0)
        )
        return min(base, self._config.max_wait_seconds)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        full_url: str | None = None,
    ) -> tuple[dict[str, Any], str | None]:
        """Returns JSON body and Link header value."""
        url = full_url or f"{self._config.base_url}{path}"
        last_error: Exception | None = None

        for attempt in range(1, self._config.max_retries + 1):
            self._rate_limiter.wait()
            try:
                response = self._session.request(
                    method,
                    url,
                    params=None if full_url else params,
                    timeout=self._config.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                logger.warning("Shopify request failed (attempt %s): %s", attempt, exc)
                if attempt < self._config.max_retries:
                    time.sleep(self._wait_retry(attempt))
                continue

            link_header = response.headers.get("Link")

            if response.status_code == RATE_LIMIT_STATUS:
                retry_after = float(
                    response.headers.get("Retry-After", self._wait_retry(attempt))
                )
                logger.warning("Shopify rate limit; sleeping %.1fs", retry_after)
                time.sleep(retry_after)
                continue

            if response.status_code >= 500:
                last_error = ShopifyAPIError(
                    f"Shopify server error {response.status_code}",
                    response.status_code,
                    response.text,
                )
                if attempt < self._config.max_retries:
                    time.sleep(self._wait_retry(attempt))
                continue

            if not response.ok:
                raise ShopifyAPIError(
                    f"Shopify API error {response.status_code}: {response.text[:500]}",
                    response.status_code,
                    response.text,
                )

            if response.status_code == 204 or not response.content:
                return {}, link_header

            return response.json(), link_header

        raise ShopifyAPIError(
            f"Shopify request failed after {self._config.max_retries} attempts: {last_error}"
        )

    def _paginate(
        self,
        path: str,
        resource_key: str,
        params: dict[str, Any],
    ) -> Iterator[dict[str, Any]]:
        params = {**params, "limit": SHOPIFY_PAGE_LIMIT}
        next_url: str | None = None
        page = 0

        while True:
            page += 1
            if next_url:
                data, link_header = self._request("GET", path, full_url=next_url)
            else:
                data, link_header = self._request("GET", path, params=params)

            for item in data.get(resource_key, []):
                yield item

            links = _parse_link_header(link_header)
            next_url = links.get("next")
            if not next_url:
                break
            logger.info("Shopify pagination: fetched page %s of %s", page, resource_key)

    @staticmethod
    def _iso_range(start_date: str, end_date: str) -> tuple[str, str]:
        start = f"{start_date}T00:00:00+00:00"
        end = f"{end_date}T23:59:59+00:00"
        return start, end

    def iter_orders(self, start_date: str, end_date: str) -> Iterator[dict[str, Any]]:
        created_min, created_max = self._iso_range(start_date, end_date)
        params = {
            "status": "any",
            "created_at_min": created_min,
            "created_at_max": created_max,
        }
        logger.info(
            "Fetching Shopify orders from %s to %s",
            created_min,
            created_max,
        )
        yield from self._paginate("/orders.json", "orders", params)

    def get_product(self, product_id: int | None) -> dict[str, Any] | None:
        if not product_id:
            return None
        if product_id in self._product_cache:
            return self._product_cache[product_id]

        try:
            data, _ = self._request("GET", f"/products/{product_id}.json")
            product = data.get("product")
            if product:
                self._product_cache[product_id] = product
            return product
        except ShopifyAPIError as exc:
            if exc.status_code == 404:
                logger.warning("Product %s not found", product_id)
                return None
            raise

    def get_location(self, location_id: int | None) -> dict[str, Any] | None:
        if not location_id:
            return None
        if location_id in self._location_cache:
            return self._location_cache[location_id]

        try:
            data, _ = self._request("GET", f"/locations/{location_id}.json")
            location = data.get("location")
            if location:
                self._location_cache[location_id] = location
            return location
        except ShopifyAPIError as exc:
            if exc.status_code == 404:
                return None
            raise

    def get_fulfillment_orders(self, order_id: int) -> list[dict[str, Any]]:
        try:
            data, _ = self._request(
                "GET", f"/orders/{order_id}/fulfillment_orders.json"
            )
            return data.get("fulfillment_orders", [])
        except ShopifyAPIError as exc:
            logger.warning("Fulfillment orders for order %s: %s", order_id, exc)
            return []

    def clear_caches(self) -> None:
        self._product_cache.clear()
        self._location_cache.clear()
