"""Obtain and cache Shopify Admin API access tokens via client credentials grant."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from config import BASE_DIR, ShopifyConfig

logger = logging.getLogger(__name__)

TOKEN_CACHE_FILE = BASE_DIR / ".shopify_token_cache.json"
TOKEN_REFRESH_BUFFER_SECONDS = 300


@dataclass
class TokenInfo:
    access_token: str
    scope: str
    expires_at: float

    @property
    def is_valid(self) -> bool:
        return time.time() < (self.expires_at - TOKEN_REFRESH_BUFFER_SECONDS)


class ShopifyAuthError(Exception):
    pass


def _normalize_shop_domain(shop_domain: str) -> str:
    domain = shop_domain.replace("https://", "").replace("http://", "").strip("/")
    if not domain.endswith(".myshopify.com"):
        domain = f"{domain}.myshopify.com"
    return domain


def _load_cached_token(shop_domain: str) -> TokenInfo | None:
    if not TOKEN_CACHE_FILE.exists():
        return None
    try:
        data = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
        entry = data.get(shop_domain)
        if not entry:
            return None
        token = TokenInfo(
            access_token=entry["access_token"],
            scope=entry.get("scope", ""),
            expires_at=float(entry["expires_at"]),
        )
        return token if token.is_valid else None
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        logger.debug("Token cache read failed: %s", exc)
        return None


def _save_cached_token(shop_domain: str, token: TokenInfo) -> None:
    data: dict[str, Any] = {}
    if TOKEN_CACHE_FILE.exists():
        try:
            data = json.loads(TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    data[shop_domain] = {
        "access_token": token.access_token,
        "scope": token.scope,
        "expires_at": token.expires_at,
    }
    TOKEN_CACHE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.debug("Cached Shopify token for %s", shop_domain)


def fetch_access_token(config: ShopifyConfig) -> TokenInfo:
    """
    Exchange client_id + client_secret for an Admin API access token.

    See: https://shopify.dev/docs/apps/build/authentication-authorization/access-tokens/client-credentials-grant
    """
    shop_domain = _normalize_shop_domain(config.shop_domain)
    if not config.client_id or not config.client_secret:
        raise ShopifyAuthError(
            "SHOPIFY_CLIENT_ID and SHOPIFY_CLIENT_SECRET are required."
        )

    url = f"https://{shop_domain}/admin/oauth/access_token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }

    try:
        response = requests.post(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=config.timeout_seconds,
        )
    except requests.RequestException as exc:
        raise ShopifyAuthError(f"Token request failed: {exc}") from exc

    if not response.ok:
        raise ShopifyAuthError(
            f"Token request failed ({response.status_code}): {response.text[:500]}"
        )

    body = response.json()
    access_token = body.get("access_token")
    if not access_token:
        raise ShopifyAuthError(f"No access_token in response: {body}")

    expires_in = int(body.get("expires_in", 86399))
    token = TokenInfo(
        access_token=access_token,
        scope=str(body.get("scope", "")),
        expires_at=time.time() + expires_in,
    )
    logger.info(
        "Obtained Shopify access token (expires in %s hours, scopes: %s)",
        round(expires_in / 3600, 1),
        token.scope or "n/a",
    )
    _save_cached_token(shop_domain, token)
    return token


def resolve_access_token(config: ShopifyConfig) -> str:
    """Return a valid access token (static override, cache, or fresh grant)."""
    if config.access_token:
        logger.info("Using SHOPIFY_ACCESS_TOKEN from environment")
        return config.access_token

    shop_domain = _normalize_shop_domain(config.shop_domain)
    cached = _load_cached_token(shop_domain)
    if cached:
        logger.info("Using cached Shopify access token")
        return cached.access_token

    return fetch_access_token(config).access_token
