from __future__ import annotations

import argparse
import csv
import json
import re
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


DEFAULT_HASH = "f6c9502ec497bb4731cf5a256bf52d0c"
DEFAULT_LANG = "it"

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
IMAGE_DIR = ROOT / "assets" / "dishcovery-images"
MENU_DATA_JS = ROOT / "js" / "menu-data.js"

CATEGORY_MAP = {
    "Antipasti": "antipasti",
    "Primi Piatti": "primi",
    "Secondi Piatti": "secondi",
    "Contorni": "contorni",
    "Pizze": "pizze",
    "Dessert": "dessert",
}


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    return unescape(re.sub(r"\s+", " ", text)).strip()


def safe_filename(value: str, fallback: str = "image") -> str:
    clean = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("_")
    return clean[:130] or fallback


def image_extension(url: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp"} else ".jpg"


def api_url(restaurant_hash: str, lang: str) -> str:
    return f"https://dishcovery.menu/api/v3/restaurants/{restaurant_hash}?lang={lang}"


def fetch_restaurant(restaurant_hash: str, lang: str) -> dict[str, Any]:
    headers = {
        "User-Agent": "Mozilla/5.0 PonteUnifiedApp/1.0",
        "Accept": "application/json,text/plain,*/*",
    }
    with httpx.Client(headers=headers, follow_redirects=True, timeout=60) as client:
        response = client.get(api_url(restaurant_hash, lang))
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict) or "menucategories" not in data:
        raise ValueError("Unexpected Dishcovery response: missing menucategories")
    return data


def download_image(client: httpx.Client, item: dict[str, Any]) -> str:
    image_url = item.get("image")
    if not image_url:
        return ""

    filename = (
        f"{item.get('id', 'item')}_"
        f"{safe_filename(item.get('name', 'image'))}"
        f"{image_extension(image_url)}"
    )
    target = IMAGE_DIR / filename
    if target.exists():
        return f"assets/dishcovery-images/{target.name}"

    try:
        response = client.get(image_url, timeout=60)
        response.raise_for_status()
    except httpx.HTTPError:
        return ""

    target.write_bytes(response.content)
    return f"assets/dishcovery-images/{target.name}"


def item_to_app_entry(
    item: dict[str, Any],
    image_path: str,
) -> dict[str, Any]:
    allergens = [
        tag.get("name")
        for tag in item.get("allergentags", [])
        if tag.get("name")
    ]
    ingredients = [
        ingredient.get("name")
        for ingredient in item.get("ingredients", [])
        if ingredient.get("name")
    ]

    return {
        "id": item.get("id"),
        "name": item.get("name", ""),
        "price": float(item.get("price") or 0),
        "description": clean_html(item.get("description")),
        "ingredients": ", ".join(ingredients),
        "allergens": allergens,
        "image": image_path,
        "payoff": item.get("payoff") or "",
        "order": item.get("order") or 0,
    }


def build_menu_data(data: dict[str, Any], download_images: bool) -> dict[str, list[dict[str, Any]]]:
    menu_data: dict[str, list[dict[str, Any]]] = {
        "antipasti": [],
        "primi": [],
        "pizze": [],
        "secondi": [],
        "contorni": [],
        "dessert": [],
        "birre": [],
        "vini_rossi": [],
        "vini_bianchi": [],
        "bevande": [],
    }

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client(
        headers={"User-Agent": "Mozilla/5.0 PonteUnifiedApp/1.0"},
        follow_redirects=True,
    ) as client:
        for category in data.get("menucategories", []):
            target_category = CATEGORY_MAP.get(category.get("name"))
            if not target_category:
                continue

            entries = []
            for item in category.get("menuentries", []):
                image_path = download_image(client, item) if download_images else ""
                entries.append(item_to_app_entry(item, image_path))

            entries.sort(key=lambda entry: (entry["order"], entry["name"]))
            menu_data[target_category].extend(entries)

    return menu_data


def write_menu_data_js(data: dict[str, Any], menu_data: dict[str, list[dict[str, Any]]]) -> None:
    metadata = {
        "name": data.get("name"),
        "description": clean_html(data.get("description")),
        "cover": data.get("cover"),
        "telephone": data.get("telephone") or "0543 29448",
        "source": "Dishcovery API v3",
    }
    MENU_DATA_JS.write_text(
        "window.menuMeta = "
        + json.dumps(metadata, ensure_ascii=False, indent=2)
        + ";\n\nwindow.menuData = "
        + json.dumps(menu_data, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )


def write_csv(data: dict[str, Any], menu_data: dict[str, list[dict[str, Any]]]) -> None:
    fieldnames = [
        "category",
        "id",
        "name",
        "price",
        "description",
        "ingredients",
        "allergens",
        "image",
    ]
    with (DATA_DIR / "menu.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for category, items in menu_data.items():
            for item in items:
                writer.writerow(
                    {
                        "category": category,
                        "id": item.get("id") or "",
                        "name": item.get("name") or "",
                        "price": f"{item.get('price'):.2f}",
                        "description": item.get("description") or "",
                        "ingredients": item.get("ingredients") or "",
                        "allergens": ", ".join(item.get("allergens") or []),
                        "image": item.get("image") or "",
                    }
                )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh unified site menu from Dishcovery.")
    parser.add_argument("--hash", default=DEFAULT_HASH, help="Dishcovery restaurant hash")
    parser.add_argument("--lang", default=DEFAULT_LANG, help="Dishcovery language")
    parser.add_argument("--from-file", action="store_true", help="Use data/restaurant.json instead of the API")
    parser.add_argument("--no-images", action="store_true", help="Do not download menu images")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if args.from_file:
        data = json.loads((DATA_DIR / "restaurant.json").read_text(encoding="utf-8"))
    else:
        data = fetch_restaurant(args.hash, args.lang)
        (DATA_DIR / "restaurant.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    menu_data = build_menu_data(data, download_images=not args.no_images)
    write_menu_data_js(data, menu_data)
    write_csv(data, menu_data)

    total = sum(len(items) for items in menu_data.values())
    print(f"Restaurant: {data.get('name')}")
    print(f"Items: {total}")
    print(f"Generated: {MENU_DATA_JS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
