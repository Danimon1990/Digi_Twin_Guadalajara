from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .validation import finite_nonnegative, require_cop, require_id, require_unit


@dataclass(frozen=True, slots=True)
class SaleOption:
    sale_option_id: str
    product_id: str
    display_name: str
    portion_label: str
    quantity: float
    unit: str
    price_cop: int | None
    price_status: str
    price_source_ref: str | None

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SaleOption":
        require_id(raw["sale_option_id"], "sale_option_id")
        require_id(raw["product_id"], "product_id")
        finite_nonnegative(raw["quantity"], "quantity")
        if raw["quantity"] == 0:
            raise ValueError("sale option quantity must be positive")
        require_unit(raw["unit"], "unit")
        status = raw["price_status"]
        if status not in {"confirmed", "pending_confirmation", "retired"}:
            raise ValueError("unsupported price_status")
        price = raw.get("price_cop")
        if price is not None:
            require_cop(price, "price_cop")
        if status == "confirmed" and price is None:
            raise ValueError("confirmed sale options require price_cop")
        if status == "pending_confirmation" and price is not None:
            raise ValueError("pending sale options must keep price_cop null")
        if status == "confirmed" and not raw.get("price_source_ref"):
            raise ValueError("confirmed sale options require price_source_ref")
        return cls(
            raw["sale_option_id"], raw["product_id"], raw["display_name"],
            raw["portion_label"], float(raw["quantity"]), raw["unit"], price,
            status, raw.get("price_source_ref"),
        )


@dataclass(frozen=True, slots=True)
class MenuPriceCatalog:
    schema_version: str
    catalog_id: str
    currency: str
    items: tuple[SaleOption, ...]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "MenuPriceCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if raw.get("schema_version") != "operations_menu_price_catalog_v1":
            raise ValueError("unsupported menu price catalog schema")
        require_id(raw["catalog_id"], "catalog_id")
        if raw.get("currency") != "COP":
            raise ValueError("menu price catalog currency must be COP")
        items = tuple(SaleOption.from_dict(item) for item in raw["items"])
        ids = [item.sale_option_id for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("menu price catalog contains duplicate sale_option_id values")
        return cls(raw["schema_version"], raw["catalog_id"], raw["currency"], items, raw)

    def by_id(self) -> dict[str, SaleOption]:
        return {item.sale_option_id: item for item in self.items}
