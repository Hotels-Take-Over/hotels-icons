#!/usr/bin/env python
import os
import uuid
import requests
from typing import List, Dict, Any

from supabase import create_client, Client  # pip install supabase
from dotenv import load_dotenv

load_dotenv()

# --- Setup ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# ========= CONFIG =========
HUGEICONS_API_URL = "https://hugeicons.com/api/icons"
ICON_STYLE_SUFFIX = "stroke-rounded"  # matches your downloaded files
ICON_VERSION = "1.0.1"  # not actually needed now, just kept for reference
OUTPUT_DIR = "icons"  # local folder where SVGs already exist
SUPABASE_TABLE = "icon_vectors"  # supabase table name
# ==========================


def get_supabase_client() -> Client:
    url = SUPABASE_URL
    key = SUPABASE_KEY

    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY must be set in environment variables"
        )

    return create_client(url, key)


def fetch_icon_list() -> List[Dict[str, Any]]:
    """Fetch the list of icons from Hugeicons API."""
    print(f"Fetching icon list from {HUGEICONS_API_URL} ...")
    resp = requests.get(HUGEICONS_API_URL, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # Expecting: { "icons": [ { name, tags, category, ... }, ... ] }
    icons = data.get("icons", [])
    print(f"Fetched {len(icons)} icons from API.")
    return icons


def ensure_output_dir():
    if not os.path.exists(OUTPUT_DIR):
        raise RuntimeError(
            f"Output directory '{OUTPUT_DIR}' does not exist. "
            "Make sure all SVGs are already downloaded there."
        )


def parse_tags(raw_tags: str, category: str | None) -> List[str]:
    """
    Convert the 'tags' string like 'parenthesis, bracket' into a list,
    and optionally include 'category' as another tag.
    """
    tags: List[str] = []
    if raw_tags:
        tags = [t.strip() for t in raw_tags.split(",") if t.strip()]

    if category:
        tags.append(category.strip())

    # Remove duplicates while keeping order
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)

    return unique_tags


def insert_icons_to_supabase(supabase: Client, rows: List[Dict[str, Any]]):
    """
    Insert rows into Supabase in chunks.
    Each row should match the icon_vectors schema:
    id, icon_name, tags, keyword, file, embedding
    """
    if not rows:
        print("No rows to insert into Supabase.")
        return

    chunk_size = 100
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        print(
            f"Inserting {len(chunk)} rows into Supabase (chunk {i // chunk_size + 1})..."
        )
        res = supabase.table(SUPABASE_TABLE).insert(chunk).execute()
        # supabase-py v2 returns a dict-like object
        if getattr(res, "error", None):
            print("  ⚠️ Supabase error:", res.error)
        else:
            print("  ✅ Inserted.")


def main():
    supabase = get_supabase_client()
    ensure_output_dir()

    icons = fetch_icon_list()

    rows_to_insert: List[Dict[str, Any]] = []

    for icon in icons:
        name = icon.get("name")  # e.g. "1st-bracket"
        raw_tags = icon.get("tags", "")  # e.g. "parenthesis, bracket"
        category = icon.get("category")  # e.g. "mathematics"

        if not name:
            continue

        # This must match how you named the downloaded files
        file_name = f"{name}-{ICON_STYLE_SUFFIX}.svg"
        local_path = os.path.join(OUTPUT_DIR, file_name)

        if not os.path.exists(local_path):
            print(f"  ⚠️ File not found for icon '{name}': {local_path} — skipping.")
            continue

        tags_list = parse_tags(raw_tags, category)

        row = {
            "id": str(uuid.uuid4()),
            "icon_name": name,
            "tags": tags_list,  # Supabase text[]; supabase-py converts list->array
            "keyword": "",  # you can also set to category if you want
            "file": file_name,  # will be used to build URL in your app
            "embedding": None,  # leave empty / null, as requested
        }

        rows_to_insert.append(row)

    print(f"Prepared {len(rows_to_insert)} rows to insert into Supabase.")
    insert_icons_to_supabase(supabase, rows_to_insert)
    print("Done.")


if __name__ == "__main__":
    main()
