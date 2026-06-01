"""Map Shopify orders and line items to report rows."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from shopify_client import ShopifyClient

logger = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "Order ID",
    "Order Number",
    "Order Date",
    "Item ID",
    "Product ID",
    "Variant ID",
    "Product SKU",
    "Product Name",
    "Product Slug",
    "Item Quantity",
    "Unit Price",
    "Item Total",
    "Order Total",
    "GST",
    "Taxable Amount",
    "IGST",
    "CGST",
    "SGST",
    "Payment Type",
    "Financial Status",
    "Customer Name",
    "Customer Email",
    "Customer Phone",
    "Shipping Address",
    "Shipping City",
    "Shipping State",
    "Shipping Country",
    "Pincode",
    "Location",
    "Warehouse Name",
    "Fulfillment Status",
    "AWB Number",
    "Courier Name",
    "Shipment Status",
    "Delivery Status",
    "Dispatch Date",
    "Delivery Date",
    "Tracking URL",
    "Created At",
    "Updated At",
]


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _customer_name(customer: dict[str, Any] | None) -> str:
    if not customer:
        return ""
    first = _safe_str(customer.get("first_name"))
    last = _safe_str(customer.get("last_name"))
    return f"{first} {last}".strip()


def _payment_type(order: dict[str, Any]) -> str:
    gateways = order.get("payment_gateway_names") or []
    if gateways:
        return ", ".join(str(g) for g in gateways)
    return _safe_str(order.get("gateway"))


def _shipping_address(order: dict[str, Any]) -> dict[str, Any]:
    return order.get("shipping_address") or order.get("billing_address") or {}


def _parse_tax_from_order(order: dict[str, Any]) -> dict[str, Decimal]:
    gst = cgst = sgst = igst = Decimal("0")
    total_tax = Decimal("0")

    for tax_line in order.get("tax_lines") or []:
        title = _safe_str(tax_line.get("title")).upper()
        amount = _to_decimal(tax_line.get("price"))
        total_tax += amount
        if "IGST" in title:
            igst += amount
        elif "CGST" in title:
            cgst += amount
        elif "SGST" in title:
            sgst += amount
        elif "GST" in title:
            gst += amount

    if gst == 0 and total_tax > 0 and igst == 0 and cgst == 0 and sgst == 0:
        gst = total_tax

    subtotal = _to_decimal(order.get("subtotal_price"))
    total_price = _to_decimal(order.get("current_total_price") or order.get("total_price"))
    taxable = subtotal if subtotal > 0 else (total_price - total_tax)
    if taxable < 0:
        taxable = Decimal("0")

    return {
        "GST": gst,
        "CGST": cgst,
        "SGST": sgst,
        "IGST": igst,
        "Taxable Amount": taxable,
        "total_tax": total_tax,
    }


def _fulfillment_snapshot(order: dict[str, Any]) -> dict[str, Any]:
    """Shipment fields from Shopify fulfillments (Velocity removed)."""
    fulfillments = order.get("fulfillments") or []
    if not fulfillments:
        return {}

    fulfillment = fulfillments[-1]
    tracking_urls = fulfillment.get("tracking_urls") or []
    status = _safe_str(fulfillment.get("status"))
    return {
        "awb_number": _safe_str(fulfillment.get("tracking_number")),
        "courier_name": _safe_str(fulfillment.get("tracking_company")),
        "shipment_status": status,
        "delivery_status": "delivered" if status == "success" else status,
        "dispatch_date": fulfillment.get("created_at"),
        "delivery_date": fulfillment.get("updated_at") if status == "success" else "",
        "tracking_url": tracking_urls[0] if tracking_urls else "",
    }


def _location_name(
    shopify: ShopifyClient,
    fulfillment_orders: list[dict[str, Any]],
) -> str:
    location_id = None
    for fo in fulfillment_orders:
        location_id = fo.get("assigned_location_id")
        if location_id:
            break
    if not location_id:
        return ""
    location = shopify.get_location(int(location_id))
    if location:
        return _safe_str(location.get("name"))
    return ""


class DataMapper:
    def __init__(self, shopify: ShopifyClient) -> None:
        self._shopify = shopify

    def map_order_to_rows(
        self,
        order: dict[str, Any],
        errors: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        order_id = order.get("id")
        order_number = order.get("order_number") or order.get("name", "").lstrip("#")
        line_items = order.get("line_items") or []

        if not line_items:
            errors.append(
                {
                    "order_id": _safe_str(order_id),
                    "order_number": _safe_str(order_number),
                    "error": "Order has no line items",
                }
            )
            return []

        order_taxes = _parse_tax_from_order(order)
        shipping = _shipping_address(order)
        customer = order.get("customer") or {}
        fulfillment_orders = self._shopify.get_fulfillment_orders(int(order_id))
        location_name = _location_name(self._shopify, fulfillment_orders)
        shipment = _fulfillment_snapshot(order)
        rows: list[dict[str, Any]] = []
        line_count = len(line_items)

        for line_item in line_items:
            product_id = line_item.get("product_id")
            product_slug = ""

            if product_id:
                try:
                    product = self._shopify.get_product(int(product_id))
                    if product:
                        product_slug = _safe_str(product.get("handle"))
                    else:
                        errors.append(
                            {
                                "order_id": _safe_str(order_id),
                                "order_number": _safe_str(order_number),
                                "error": f"Product {product_id} not found",
                            }
                        )
                except Exception as exc:
                    errors.append(
                        {
                            "order_id": _safe_str(order_id),
                            "order_number": _safe_str(order_number),
                            "error": f"Product fetch failed ({product_id}): {exc}",
                        }
                    )

            quantity = _to_decimal(line_item.get("quantity"))
            unit_price = _to_decimal(line_item.get("price"))
            item_total = quantity * unit_price

            row = {
                "Order ID": order_id,
                "Order Number": order_number,
                "Order Date": order.get("created_at"),
                "Item ID": line_item.get("id"),
                "Product ID": product_id,
                "Variant ID": line_item.get("variant_id"),
                "Product SKU": _safe_str(line_item.get("sku")),
                "Product Name": _safe_str(line_item.get("name")),
                "Product Slug": product_slug,
                "Item Quantity": float(quantity),
                "Unit Price": float(unit_price),
                "Item Total": float(item_total),
                "Order Total": float(
                    _to_decimal(
                        order.get("current_total_price") or order.get("total_price")
                    )
                ),
                "GST": float(order_taxes["GST"] / line_count),
                "Taxable Amount": float(order_taxes["Taxable Amount"] / line_count),
                "IGST": float(order_taxes["IGST"] / line_count),
                "CGST": float(order_taxes["CGST"] / line_count),
                "SGST": float(order_taxes["SGST"] / line_count),
                "Payment Type": _payment_type(order),
                "Financial Status": _safe_str(order.get("financial_status")),
                "Customer Name": _customer_name(customer),
                "Customer Email": _safe_str(customer.get("email") or order.get("email")),
                "Customer Phone": _safe_str(
                    customer.get("phone") or shipping.get("phone")
                ),
                "Shipping Address": _safe_str(shipping.get("address1")),
                "Shipping City": _safe_str(shipping.get("city")),
                "Shipping State": _safe_str(shipping.get("province")),
                "Shipping Country": _safe_str(shipping.get("country")),
                "Pincode": _safe_str(shipping.get("zip")),
                "Location": location_name,
                "Warehouse Name": location_name,
                "Fulfillment Status": _safe_str(order.get("fulfillment_status")),
                "AWB Number": shipment.get("awb_number", ""),
                "Courier Name": shipment.get("courier_name", ""),
                "Shipment Status": shipment.get("shipment_status", ""),
                "Delivery Status": shipment.get("delivery_status", ""),
                "Dispatch Date": shipment.get("dispatch_date"),
                "Delivery Date": shipment.get("delivery_date"),
                "Tracking URL": shipment.get("tracking_url", ""),
                "Created At": order.get("created_at"),
                "Updated At": order.get("updated_at"),
            }
            rows.append(row)

        return rows
