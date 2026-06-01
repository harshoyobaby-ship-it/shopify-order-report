# Shopify Order Report

Python tool that pulls Shopify orders (products, tax, fulfillments) and exports a consolidated Excel workbook—one row per line item.

## Features

- **Automatic Shopify auth** via Client ID + Client Secret (OAuth client credentials grant)
- Token cached locally (refreshes before 24h expiry)
- Date-range order export with pagination (100,000+ orders)
- Shipment fields from Shopify fulfillments (AWB, courier, tracking URL)
- Excel: `shopify_orders.xlsx` with formatted headers, filters, error log sheet

## Setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Copy `.env.example` to `.env` and configure:

   ```env
   SHOPIFY_SHOP_DOMAIN=gaddaco.myshopify.com
   SHOPIFY_CLIENT_ID=your_client_id
   SHOPIFY_CLIENT_SECRET=your_client_secret
   REPORT_START_DATE=2026-05-01
   REPORT_END_DATE=2026-05-30
   ```

3. **Shopify Dev Dashboard** (app owned by your org, installed on your store):

   - Create/open your app → **Settings** → copy **Client ID** and **Client secret**
   - Configure Admin API scopes: `read_orders`, `read_products`, `read_locations`, `read_fulfillments`
   - **Install** the app on the store

4. Run:

   ```bash
   python main.py
   ```

   Output: `reports/shopify_orders.xlsx`

## Authentication

The app calls:

```http
POST https://{shop}.myshopify.com/admin/oauth/access_token
grant_type=client_credentials&client_id=...&client_secret=...
```

This requires a **Dev Dashboard app** installed on a store **you own**. It does not work with Partner CLI tokens (`atkn_`) or admin-created custom app tokens unless you set `SHOPIFY_ACCESS_TOKEN` directly.

Optional override:

```env
SHOPIFY_ACCESS_TOKEN=shpat_...
```

## Project structure

```
├── config.py
├── shopify_auth.py      # OAuth token fetch + cache
├── shopify_client.py
├── data_mapper.py
├── excel_exporter.py
├── main.py
├── requirements.txt
├── logs/
└── reports/
```

## Velocity integration

Removed for now. Shipment columns are filled from Shopify **fulfillments** when available. Velocity can be re-added later.

## Web UI (date picker + download)

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501, choose dates, click **Generate & download Excel**.

**Deploy for a shareable link:** see [DEPLOY.md](DEPLOY.md) (Streamlit Cloud or Render, free tiers).

## License

Internal use—never commit `.env` or `.shopify_token_cache.json`.
