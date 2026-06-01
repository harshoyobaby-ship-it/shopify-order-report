# Deploy the Shopify Report Web App

The web UI lets anyone with the link (and optional password) pick **start/end dates** and **download Excel**.

Built with **Streamlit** (`app.py`).

---

## Option A: Streamlit Community Cloud (free, easiest)

1. Push this folder to **GitHub** (do not commit `.env` or `.streamlit/secrets.toml`).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select your repo, branch, and set **Main file path**: `app.py`.
4. Open **Advanced settings → Secrets** and paste (from `.streamlit/secrets.toml.example`):

```toml
SHOPIFY_SHOP_DOMAIN = "gaddaco.myshopify.com"
SHOPIFY_API_VERSION = "2026-01"
SHOPIFY_CLIENT_ID = "..."
SHOPIFY_CLIENT_SECRET = "..."
APP_PASSWORD = "your-team-password"
```

5. **Deploy**. You get a URL like `https://your-app.streamlit.app`.

**Note:** Free tier may time out on very large date ranges (500+ orders ≈ 5+ minutes). Use shorter ranges or upgrade.

---

## Option B: Render (free)

1. Push to GitHub.
2. [render.com](https://render.com) → **New → Blueprint** → connect repo (`render.yaml` is included).
3. Set environment variables in the Render dashboard:
   - `SHOPIFY_SHOP_DOMAIN`
   - `SHOPIFY_CLIENT_ID`
   - `SHOPIFY_CLIENT_SECRET`
   - `APP_PASSWORD` (recommended)
4. Deploy. Render provides a public URL.

---

## Run locally (test before deploy)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens `http://localhost:8501`. Uses `.env` for Shopify credentials.

Optional password: add to `.env`:

```env
APP_PASSWORD=your-password
```

---

## Security checklist

- Always set **APP_PASSWORD** on any public URL.
- Never commit `.env`, `secrets.toml`, or `.shopify_token_cache.json`.
- The Excel file contains customer PII—treat download links like confidential data.
- Rotate Shopify client secret if it was ever exposed in chat or git history.

---

## CLI (unchanged)

```bash
python main.py
```

Uses `REPORT_START_DATE` / `REPORT_END_DATE` from `.env`.
