from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain.catalog import ProductCatalog


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
        catalog_file = config.get("product_catalog_file")
        if catalog_file:
            catalog = ProductCatalog.load(scenario_path.parent / catalog_file)
            config["products"] = catalog.raw["products"]
            config["product_catalog_snapshot"] = catalog.raw
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
        product_ids = {item["product_id"] for item in config["products"]}
        for visit in config["visits"]:
            for line in visit.get("order", {}).get("lines", []):
                if line["product_id"] not in product_ids:
                    raise ValueError(f"unknown scenario product {line['product_id']}")
        return cls(
            config["scenario_id"], config["model_version"], config["layout_version"],
            float(stop), config,
        )
