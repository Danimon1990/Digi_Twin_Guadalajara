from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Product
from .validation import finite_nonnegative, require_cop, require_id


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    product: Product
    handling_time: dict[str, Any]
    price_evidence: str
    needs_price_confirmation: bool

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CatalogProduct":
        product = Product(
            product_id=raw["product_id"],
            name=raw["name"],
            category=raw["category"],
            sale_unit=raw["sale_unit"],
            default_price_cop=raw.get("default_price_cop"),
            tags=tuple(raw.get("tags", [])),
        )
        handling = raw["handling_time"]
        for field in ("selection_setup_s", "selection_per_unit_s"):
            finite_nonnegative(handling[field], f"handling_time.{field}")
        if handling.get("evidence") != "synthetic":
            raise ValueError("catalog handling defaults must be explicitly synthetic")
        if handling.get("replaceable") is not True:
            raise ValueError("catalog handling defaults must be marked replaceable")
        if product.default_price_cop is not None:
            require_cop(product.default_price_cop, "default_price_cop")
        return cls(
            product, handling, raw["price_evidence"],
            bool(raw["needs_price_confirmation"]),
        )


@dataclass(frozen=True, slots=True)
class ProductCatalog:
    schema_version: str
    currency: str
    time_unit: str
    source_ref: str
    products: tuple[CatalogProduct, ...]
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "ProductCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        require_id(raw["schema_version"], "schema_version")
        if raw["currency"] != "COP":
            raise ValueError("product catalog currency must be COP")
        if raw["time_unit"] != "seconds":
            raise ValueError("product catalog time_unit must be seconds")
        products = tuple(CatalogProduct.from_dict(item) for item in raw["products"])
        ids = [item.product.product_id for item in products]
        if len(ids) != len(set(ids)):
            raise ValueError("product catalog contains duplicate product_id values")
        return cls(
            raw["schema_version"], raw["currency"], raw["time_unit"],
            raw["source_ref"], products, raw,
        )

    def by_id(self) -> dict[str, CatalogProduct]:
        return {item.product.product_id: item for item in self.products}
