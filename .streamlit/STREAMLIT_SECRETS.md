# Streamlit Cloud secrets

In [share.streamlit.io](https://share.streamlit.io) → your app → **Settings** → **Secrets**, paste:

```toml
SHOPIFY_SHOP_DOMAIN = "gaddaco.myshopify.com"
SHOPIFY_API_VERSION = "2026-01"
SHOPIFY_CLIENT_ID = "paste_from_env"
SHOPIFY_CLIENT_SECRET = "paste_from_env"
APP_PASSWORD = "choose-a-team-password"
```

Use the same values as your local `.env` file (never commit `.env`).
