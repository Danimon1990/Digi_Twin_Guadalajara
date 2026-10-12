from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.catalog import ProductCatalog
from ..domain.pricing import MenuPriceCatalog


@dataclass(frozen=True, slots=True)
class Scenario:
    scenario_id: str
    model_version: str
    layout_version: str
    stop_time_s: float
    config: dict[str, Any]

    @classmethod
    def load(cls, path: str | Path) -> "Scenario":
        scenario_path = Path(path)
        config = json.loads(scenario_path.read_text(encoding="utf-8"))
        staffing_file = config.get("staffing_profile_file")
        if staffing_file:
            staffing = json.loads(
                (scenario_path.parent / staffing_file).read_text(encoding="utf-8")
            )
            if staffing.get("schema_version") != "operations_staffing_profile_v1":
                raise ValueError("unsupported staffing profile schema")
            config["workers"] = staffing["workers"]
            config["staffing_profile_snapshot"] = staffing
        catalog_file = config.get("product_catalog_file")
        if catalog_file:
            catalog = ProductCatalog.load(scenario_path.parent / catalog_file)
            config["products"] = catalog.raw["products"]
            config["product_catalog_snapshot"] = catalog.raw
        price_catalog_file = config.get("menu_price_catalog_file")
        if not price_catalog_file:
            raise ValueError("scenario requires menu_price_catalog_file")
        price_catalog = MenuPriceCatalog.load(scenario_path.parent / price_catalog_file)
        config["menu_price_catalog_snapshot"] = price_catalog.raw
        price_options = price_catalog.by_id()
        required = {"scenario_id", "model_version", "layout_version", "stop_time_s",
                    "workers", "resources", "products", "visits", "durations"}
        missing = sorted(required.difference(config))
        if missing:
            raise ValueError(f"scenario missing fields: {', '.join(missing)}")
        stop = config["stop_time_s"]
        if not isinstance(stop, (int, float)) or not math.isfinite(stop) or stop <= 0:
            raise ValueError("stop_time_s must be finite and positive")
        if config.get("evidence") != "synthetic":
            raise ValueError("the built-in simulation accepts explicitly synthetic scenarios")
        relationships = config.get("relationships", {})
        if relationships.get("payment_start") not in {"after_ready", "after_handover"}:
            raise ValueError("payment_start must be after_ready or after_handover")
        if relationships.get("server_release") not in {"after_ready", "after_handover", "after_payment"}:
            raise ValueError("server_release must be after_ready, after_handover, or after_payment")
        handover_start = relationships.get("handover_start", "after_ready")
        if handover_start not in {"after_ready", "after_payment"}:
            raise ValueError("handover_start must be after_ready or after_payment")
        if handover_start == "after_payment" and relationships.get("payment_start") != "after_ready":
            raise ValueError("handover_start after_payment requires payment_start after_ready")
        product_ids = {item["product_id"] for item in config["products"]}
        for visit in config["visits"]:
            order = visit.get("order")
            if order is None:
                continue
            if "amount_cop" in order:
                raise ValueError("order amount_cop must be derived from menu_prices.json")
            known_total = 0
            all_prices_known = True
            for line in order.get("lines", []):
                if line["product_id"] not in product_ids:
                    raise ValueError(f"unknown scenario product {line['product_id']}")
                option_id = line.get("sale_option_id")
                if option_id not in price_options:
                    raise ValueError(f"unknown sale option {option_id!r}")
                option = price_options[option_id]
                if option.product_id != line["product_id"]:
                    raise ValueError("sale option product does not match order line product")
                if option.unit != line["unit"]:
                    raise ValueError("sale option unit does not match order line unit")
                line["unit_price_cop"] = option.price_cop
                if option.price_cop is None:
                    all_prices_known = False
                else:
                    line_total = float(line["quantity"]) * option.price_cop
                    if not line_total.is_integer():
                        raise ValueError("order line produces a fractional COP amount")
                    known_total += int(line_total)
            order["amount_cop"] = known_total if all_prices_known else None
            order["price_status"] = "confirmed" if all_prices_known else "unknown"
        return cls(
            config["scenario_id"], config["model_version"], config["layout_version"],
            float(stop), config,
        )
