"""
Seeds the database with a realistic electronics catalog: laptops,
accessories, and gaming products, plus merchant-curated upsell/cross-sell
relationships and starting inventory. Safe to re-run - it clears and
re-creates catalog data each time so demos start from a known state.

Usage (from backend/):
    python scripts/seed_database.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import Base, engine, session_scope
from app.models.catalog import Inventory, Product, ProductRelation
from app.models.users import Merchant
import app.models  # noqa: F401 - register all tables

import hashlib


LAPTOPS = [
    dict(sku="LT-001", name="AeroBook 14 Slim", price=54999, portability=0.9, performance=0.5,
         tags=["coding", "college", "office", "travel"],
         specs={"cpu": "Intel i5-1240P", "ram": "16GB", "storage": "512GB SSD", "display": "14\" FHD", "weight_kg": 1.2},
         desc="A 1.2kg ultrabook built for students and developers who need to carry it everywhere."),
    dict(sku="LT-002", name="AeroBook 14 Pro", price=68999, portability=0.85, performance=0.65,
         tags=["coding", "college", "office", "editing", "travel"],
         specs={"cpu": "Intel i7-1260P", "ram": "16GB", "storage": "1TB SSD", "display": "14\" 2.2K", "weight_kg": 1.3},
         desc="The Pro variant adds a sharper display and more storage for creative and dev work on the move."),
    dict(sku="LT-003", name="ForgeStrike 15 Gaming", price=79999, portability=0.35, performance=0.95,
         tags=["gaming", "coding", "editing"],
         specs={"cpu": "AMD Ryzen 7 7735HS", "gpu": "RTX 4060", "ram": "16GB", "storage": "1TB SSD",
                "display": "15.6\" 165Hz", "weight_kg": 2.3},
         desc="A proper gaming rig with an RTX 4060, comfortable for coding sessions too."),
    dict(sku="LT-004", name="ForgeStrike 16 Gaming Max", price=118999, portability=0.25, performance=1.0,
         tags=["gaming", "editing"],
         specs={"cpu": "AMD Ryzen 9 7940HX", "gpu": "RTX 4070", "ram": "32GB", "storage": "1TB SSD",
                "display": "16\" 240Hz", "weight_kg": 2.6},
         desc="The flagship gaming laptop for players who refuse to compromise on frame rate."),
    dict(sku="LT-005", name="CampusLite 11", price=32999, portability=0.95, performance=0.25,
         tags=["college", "office", "travel"],
         specs={"cpu": "Intel N200", "ram": "8GB", "storage": "256GB SSD", "display": "11.6\" HD", "weight_kg": 0.98},
         desc="The lightest, most affordable option for note-taking, browsing, and office work."),
    dict(sku="LT-006", name="StudioWorks 15 Creator", price=94999, portability=0.4, performance=0.85,
         tags=["editing", "coding"],
         specs={"cpu": "Intel i9-13900H", "gpu": "RTX 4050", "ram": "32GB", "storage": "1TB SSD",
                "display": "15.6\" 4K OLED", "weight_kg": 1.9},
         desc="A colour-accurate 4K OLED display and serious CPU power for video and photo editing."),
    dict(sku="LT-007", name="AeroBook Air 13", price=61999, portability=1.0, performance=0.45,
         tags=["college", "office", "travel", "coding"],
         specs={"cpu": "Apple-class ARM equivalent", "ram": "16GB", "storage": "512GB SSD",
                "display": "13.3\" Retina-class", "weight_kg": 1.05},
         desc="Fanless, silent, and the most portable laptop in the lineup at just over a kilogram."),
    dict(sku="LT-008", name="ValueLine 14 Everyday", price=39999, portability=0.8, performance=0.35,
         tags=["college", "office"],
         specs={"cpu": "Intel i3-1215U", "ram": "8GB", "storage": "512GB SSD", "display": "14\" FHD", "weight_kg": 1.4},
         desc="A dependable everyday laptop for students on a tighter budget."),
    dict(sku="LT-009", name="ForgeStrike 14 Gaming Compact", price=69999, portability=0.55, performance=0.8,
         tags=["gaming", "coding", "college"],
         specs={"cpu": "AMD Ryzen 7 7840HS", "gpu": "RTX 4050", "ram": "16GB", "storage": "512GB SSD",
                "display": "14\" 144Hz", "weight_kg": 1.7},
         desc="A rare combination: genuinely portable at 1.7kg while still packing an RTX 4050."),
    dict(sku="LT-010", name="DevMachine Pro 16", price=104999, portability=0.3, performance=0.9,
         tags=["coding", "editing"],
         specs={"cpu": "Intel i9-13980HX", "ram": "32GB", "storage": "2TB SSD", "display": "16\" QHD+", "weight_kg": 2.1},
         desc="Built for heavy compilation, containers, and multi-monitor development workflows."),
]

ACCESSORIES = [
    dict(sku="AC-001", name="GlidePoint Wireless Mouse", price=1499, tags=["coding", "gaming", "office"],
         specs={"dpi": "16000", "battery": "70 days", "connectivity": "2.4GHz + Bluetooth"},
         desc="A precise, low-latency wireless mouse that pairs well with both productivity and gaming laptops."),
    dict(sku="AC-002", name="ClickMech Mechanical Keyboard", price=3499, tags=["coding", "gaming"],
         specs={"switch": "Brown tactile", "layout": "TKL", "backlight": "RGB"},
         desc="A tactile mechanical keyboard for long coding sessions and gaming alike."),
    dict(sku="AC-003", name="AudioPeak Wireless Headset", price=2999, tags=["gaming", "office"],
         specs={"driver": "50mm", "mic": "detachable boom", "battery": "30 hrs"},
         desc="Comfortable over-ear headset with a detachable mic for calls and gaming."),
    dict(sku="AC-004", name="CarryLite 14-inch Laptop Bag", price=1999, tags=["travel", "college"],
         specs={"material": "water-resistant nylon", "capacity": "14 inch + accessories"},
         desc="A padded, weather-resistant bag sized for 13-15 inch laptops."),
    dict(sku="AC-005", name="PowerHub 100W USB-C Charger", price=2499, tags=["travel", "office", "college"],
         specs={"output": "100W USB-C PD", "ports": 3},
         desc="A compact GaN charger that can power a laptop and two phones simultaneously."),
    dict(sku="AC-006", name="ViewMax 27-inch Monitor", price=15999, tags=["coding", "office", "editing"],
         specs={"resolution": "2560x1440", "refresh": "75Hz", "panel": "IPS"},
         desc="A sharp QHD monitor for extending a laptop into a proper desk setup."),
    dict(sku="AC-007", name="DockAll USB-C Hub 8-in-1", price=2799, tags=["coding", "office", "travel"],
         specs={"ports": "HDMI, 3xUSB-A, SD, Ethernet, USB-C PD"},
         desc="An 8-in-1 hub that turns a single USB-C port into a full desktop connection set."),
    dict(sku="AC-008", name="CoolBase Laptop Stand + Fan", price=1799, tags=["coding", "gaming", "editing"],
         specs={"fans": 2, "material": "aluminium"},
         desc="An angled aluminium stand with active cooling for long gaming or render sessions."),
]

GAMING = [
    dict(sku="GM-001", name="StrikePad Wireless Controller", price=3999, tags=["gaming"],
         specs={"connectivity": "Bluetooth + 2.4GHz", "battery": "20 hrs"},
         desc="A precise wireless controller compatible with most modern gaming laptops."),
    dict(sku="GM-002", name="ThroneSeat Gaming Chair", price=12999, tags=["gaming"],
         specs={"material": "PU leather", "recline": "150 degrees"},
         desc="An ergonomic gaming chair for long sessions."),
    dict(sku="GM-003", name="FrameRate 165Hz Portable Monitor", price=17999, tags=["gaming", "travel"],
         specs={"resolution": "1920x1080", "refresh": "165Hz", "size": "15.6 inch"},
         desc="A slim portable monitor for a dual-screen gaming setup on the road."),
    dict(sku="GM-004", name="GripZone Gaming Mouse Pad XL", price=999, tags=["gaming"],
         specs={"size": "900x400mm"},
         desc="An extra-large mouse pad covering keyboard and mouse space."),
    dict(sku="GM-005", name="StreamCast USB Microphone", price=4499, tags=["gaming", "editing"],
         specs={"pattern": "cardioid", "sample_rate": "48kHz"},
         desc="A USB condenser mic for streaming or content creation alongside gaming."),
    dict(sku="GM-006", name="ChillFlow RGB Cooling Pad", price=2299, tags=["gaming"],
         specs={"fans": 5, "lighting": "RGB"},
         desc="A five-fan cooling pad to keep gaming laptops thermally happy during long sessions."),
]

# (product_sku, related_sku, relation_type, reason, bundle_discount_percent)
RELATIONS = [
    ("LT-003", "AC-001", "cross_sell", "compatible with the laptop and useful for both coding and gaming", 5.0),
    ("LT-003", "GM-006", "cross_sell", "keeps the gaming laptop's CPU/GPU cool under sustained load", 0.0),
    ("LT-009", "AC-001", "cross_sell", "a precise wireless mouse pairs well with this compact gaming laptop", 5.0),
    ("LT-009", "GM-001", "cross_sell", "adds a wireless controller for the gaming use case you mentioned", 0.0),
    ("LT-004", "AC-006", "upsell", "a QHD monitor complements the flagship GPU for a full desk setup", 0.0),
    ("LT-004", "GM-002", "cross_sell", "an ergonomic chair for extended high-performance gaming sessions", 0.0),
    ("LT-001", "AC-005", "cross_sell", "a compact fast charger for a laptop this portable", 0.0),
    ("LT-001", "AC-004", "cross_sell", "a fitted bag matches the laptop's 14-inch, travel-friendly design", 0.0),
    ("LT-002", "AC-007", "cross_sell", "a USB-C hub adds ports this ultrabook doesn't have built in", 0.0),
    ("LT-007", "AC-004", "cross_sell", "a protective bag suited to this laptop's slim profile", 0.0),
    ("LT-006", "AC-006", "upsell", "a second QHD display extends the creator workflow this laptop is built for", 0.0),
    ("LT-010", "AC-002", "cross_sell", "a mechanical keyboard for extended development sessions", 0.0),
    ("LT-008", "AC-004", "cross_sell", "an affordable bag to match this budget-friendly laptop", 0.0),
    ("LT-005", "AC-005", "cross_sell", "a compact charger to match this ultra-light laptop", 0.0),
]

INVENTORY_DEFAULT = 25


def _upsert_product(db, data: dict, category: str) -> Product:
    """Updates the product in place if the SKU already exists, rather than
    deleting and recreating it. Deleting is unsafe once a product has been
    referenced by cart items, order items, or product relations (re-running
    the seed script against a DB that already has demo activity in it is a
    normal thing to do, and must not raise a foreign-key error)."""
    from sqlalchemy import select

    existing = db.execute(select(Product).where(Product.sku == data["sku"])).scalar_one_or_none()

    if existing:
        existing.name = data["name"]
        existing.category = category
        existing.description = data["desc"]
        existing.price = float(data["price"])
        existing.specs = data["specs"]
        existing.tags = data["tags"]
        existing.portability_score = data.get("portability", 0.5)
        existing.performance_score = data.get("performance", 0.5)
        existing.is_active = True
        db.flush()
        inv = db.execute(select(Inventory).where(Inventory.product_id == existing.id)).scalar_one_or_none()
        if inv is None:
            db.add(Inventory(product_id=existing.id, quantity_available=INVENTORY_DEFAULT, reserved=0))
        else:
            inv.quantity_available = INVENTORY_DEFAULT
            inv.reserved = 0
        return existing

    product = Product(
        sku=data["sku"],
        name=data["name"],
        category=category,
        description=data["desc"],
        price=float(data["price"]),
        specs=data["specs"],
        tags=data["tags"],
        portability_score=data.get("portability", 0.5),
        performance_score=data.get("performance", 0.5),
    )
    db.add(product)
    db.flush()
    db.add(Inventory(product_id=product.id, quantity_available=INVENTORY_DEFAULT, reserved=0))
    return product


def seed() -> None:
    Base.metadata.create_all(bind=engine)

    with session_scope() as db:
        from sqlalchemy import select

        # Clear relations first (FK dependency)
        db.query(ProductRelation).delete()

        by_sku: dict[str, Product] = {}
        for item in LAPTOPS:
            by_sku[item["sku"]] = _upsert_product(db, item, "laptop")
        for item in ACCESSORIES:
            by_sku[item["sku"]] = _upsert_product(db, item, "accessory")
        for item in GAMING:
            by_sku[item["sku"]] = _upsert_product(db, item, "gaming")

        for sku, related_sku, relation_type, reason, discount in RELATIONS:
            db.add(
                ProductRelation(
                    product_id=by_sku[sku].id,
                    related_product_id=by_sku[related_sku].id,
                    relation_type=relation_type,
                    reason=reason,
                    bundle_discount_percent=discount,
                )
            )

        merchant = db.execute(select(Merchant).where(Merchant.username == "merchant")).scalar_one_or_none()
        if merchant is None:
            password_hash = hashlib.sha256(b"demo-password").hexdigest()
            db.add(Merchant(name="RazorSell Demo Merchant", username="merchant", password_hash=password_hash))

        print(f"Seeded {len(LAPTOPS)} laptops, {len(ACCESSORIES)} accessories, {len(GAMING)} gaming products.")
        print(f"Seeded {len(RELATIONS)} product relations.")


if __name__ == "__main__":
    seed()
