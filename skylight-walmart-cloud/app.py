from __future__ import annotations

import hmac
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

from src.extract import UploadedImage, extract_grocery_list
from src.models import GroceryItem
from src.normalize import build_search_query, merge_exact_items, parse_text_list

st.set_page_config(page_title="Skylight → Walmart Cart", page_icon="🛒", layout="wide")

COLUMNS = ["include", "item", "quantity", "unit", "notes", "search_query", "packages"]
PROJECT_DIR = Path(__file__).resolve().parent


def secret_value(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value).strip() if value is not None else default


def require_household_access() -> None:
    expected = secret_value("APP_PASSWORD")
    if not expected or st.session_state.get("household_authenticated"):
        return

    st.title("Skylight → Walmart Cart")
    st.caption("Enter the household access code to continue.")
    supplied = st.text_input("Household access code", type="password")
    if st.button("Unlock", type="primary"):
        if hmac.compare_digest(supplied, expected):
            st.session_state.household_authenticated = True
            st.rerun()
        else:
            st.error("That access code was not recognized.")
    st.stop()


@st.cache_data
def build_extension_zip() -> bytes:
    extension_dir = PROJECT_DIR / "extension"
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(extension_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, arcname=f"skylight-walmart-extension/{file_path.relative_to(extension_dir)}")
    return output.getvalue()


def empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def items_to_frame(items: list[GroceryItem]) -> pd.DataFrame:
    rows = []
    for item in merge_exact_items(items):
        rows.append({
            "include": True,
            "item": item.name,
            "quantity": float(item.quantity),
            "unit": item.unit,
            "notes": item.notes,
            "search_query": build_search_query(item),
            "packages": 1,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def add_items(items: list[GroceryItem]) -> None:
    incoming = items_to_frame(items)
    if st.session_state.items.empty:
        st.session_state.items = incoming
    else:
        combined = pd.concat([st.session_state.items, incoming], ignore_index=True)
        # Merge only exact item/unit/notes rows and preserve editable fields.
        grouped = []
        grouping_keys = [
            combined[column].fillna("").astype(str).str.lower()
            for column in ["item", "unit", "notes"]
        ]
        for (_, _, _), group in combined.groupby(grouping_keys, sort=False, dropna=False):
            first = group.iloc[0].to_dict()
            first["quantity"] = pd.to_numeric(group["quantity"], errors="coerce").fillna(0).sum()
            first["packages"] = int(pd.to_numeric(group["packages"], errors="coerce").fillna(1).max())
            first["include"] = bool(group["include"].any())
            grouped.append(first)
        st.session_state.items = pd.DataFrame(grouped, columns=COLUMNS)


require_household_access()

if "items" not in st.session_state:
    st.session_state.items = empty_frame()

st.title("Skylight → Walmart Cart")
st.caption("Turn a Skylight grocery list into a reviewed cart plan for your regular Walmart account—without Instacart. Cloud sessions are temporary; download the cart before closing the app.")

with st.sidebar:
    st.subheader("Household defaults")
    preferred_store = st.text_input(
        "Walmart store or ZIP (reference only)",
        placeholder="e.g. 80920 or North Colorado Springs",
        help="The extension uses the store already selected in Walmart. This field is included in the export as a reminder.",
    )
    mode = st.selectbox(
        "Extension mode",
        ["Assisted review", "Auto-pick cheapest confident match"],
        help="Assisted review shows candidate products on each Walmart search page. Auto mode is faster but should be used cautiously.",
    )
    st.info("The tool never submits an order or payment. Final review and checkout stay in Walmart.")
    st.download_button(
        "Download Chrome extension",
        data=build_extension_zip(),
        file_name="skylight-walmart-extension.zip",
        mime="application/zip",
        use_container_width=True,
        help="Unzip it, then load the contained folder from chrome://extensions.",
    )

input_tab, review_tab, export_tab = st.tabs(["1. Import list", "2. Review items", "3. Export to extension"])

with input_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Paste a list")
        pasted = st.text_area(
            "One item per line",
            height=260,
            placeholder="2 cans diced tomatoes\n1.5 lb chicken breast\nshredded cheddar (sharp)\nbananas",
        )
        if st.button("Parse pasted list", type="primary", use_container_width=True):
            parsed = parse_text_list(pasted)
            if parsed:
                add_items(parsed)
                st.success(f"Added {len(parsed)} line(s). Review them in the next tab.")
            else:
                st.warning("No list items were found.")

    with right:
        st.subheader("Upload Skylight screenshots")
        uploads = st.file_uploader(
            "PNG, JPG, JPEG, or WEBP",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )
        configured_api_key = secret_value("OPENAI_API_KEY")
        configured_model = secret_value("OPENAI_MODEL", "gpt-5.6")
        if configured_api_key:
            st.success("Screenshot extraction is enabled for this deployed app.")
            api_key = configured_api_key
        else:
            api_key = st.text_input(
                "OpenAI API key",
                type="password",
                help="Used only for this extraction request. It is not written to the cart export.",
            )
        model = st.text_input("Vision model", value=configured_model)
        extra_text = st.text_area(
            "Optional notes or pasted list to include with screenshots",
            height=90,
            placeholder="Ignore crossed-out items; 'milk' means whole milk.",
        )
        if st.button("Extract screenshot list", type="primary", use_container_width=True):
            if not uploads:
                st.warning("Upload at least one screenshot.")
            else:
                try:
                    images = [
                        UploadedImage(data=file.getvalue(), mime_type=file.type or "image/png")
                        for file in uploads
                    ]
                    with st.spinner("Reading the Skylight list…"):
                        result = extract_grocery_list(
                            api_key=api_key,
                            model=model,
                            images=images,
                            pasted_text=extra_text,
                        )
                    add_items(result.items)
                    st.success(f"Extracted {len(result.items)} item(s). Review them before exporting.")
                except Exception as exc:  # Streamlit should show a useful, non-fatal error.
                    st.error(f"Could not extract the screenshots: {exc}")

    st.divider()
    st.markdown(
        "**Current MVP boundary:** screenshots are converted into grocery lines, but the tool does not infer the full ingredients "
        "for a meal unless Skylight already put those ingredients on the list."
    )

with review_tab:
    st.subheader("Clean up quantities and Walmart searches")
    st.write(
        "Edit any misread item, add brand or dietary notes, and adjust the number of packages. "
        "The extension searches using the `search_query` field."
    )

    if st.session_state["grocery_items_df"].empty:
        st.info("Import a pasted list or screenshots first.")
    else:
        edited = st.data_editor(
            st.session_state.items,
            use_container_width=True,
            num_rows="dynamic",
            hide_index=True,
            column_config={
                "include": st.column_config.CheckboxColumn("Include", default=True),
                "item": st.column_config.TextColumn("Item", required=True),
                "quantity": st.column_config.NumberColumn("Needed", min_value=0.0, step=0.25),
                "unit": st.column_config.TextColumn("Unit"),
                "notes": st.column_config.TextColumn("Preferences / notes"),
                "search_query": st.column_config.TextColumn("Walmart search", required=True),
                "packages": st.column_config.NumberColumn(
                    "Packages to add", min_value=1, max_value=20, step=1, default=1
                ),
            },
            key="item_editor",
        )
        st.session_state.items = edited

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("Rebuild search queries", use_container_width=True):
                rebuilt = edited.copy()
                rebuilt["search_query"] = rebuilt.apply(
                    lambda row: build_search_query(
                        GroceryItem(
                            name=str(row.get("item", "")),
                            quantity=float(row.get("quantity", 1) or 1),
                            unit=str(row.get("unit", "item") or "item"),
                            notes=str(row.get("notes", "") or ""),
                        )
                    ),
                    axis=1,
                )
                st.session_state.items = rebuilt
                st.rerun()
        with c2:
            if st.button("Remove unchecked rows", use_container_width=True):
                st.session_state.items = edited[edited["include"]].reset_index(drop=True)
                st.rerun()
        with c3:
            if st.button("Clear all", use_container_width=True):
                st.session_state.items = empty_frame()
                st.rerun()

with export_tab:
    st.subheader("Create the extension handoff file")
    included = st.session_state.items
    if not included.empty:
        included = included[included["include"]].copy()

    if included.empty:
        st.info("There are no included items to export.")
    else:
        export_items = []
        for idx, row in included.reset_index(drop=True).iterrows():
            export_items.append({
                "id": f"item-{idx + 1}",
                "name": str(row.get("item", "")).strip(),
                "quantity": float(row.get("quantity", 1) or 1),
                "unit": str(row.get("unit", "item") or "item").strip(),
                "notes": str(row.get("notes", "") or "").strip(),
                "search_query": str(row.get("search_query", row.get("item", ""))).strip(),
                "packages": max(1, int(row.get("packages", 1) or 1)),
            })

        payload = {
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "Skylight grocery list",
            "store_note": preferred_store.strip(),
            "mode": "auto" if mode.startswith("Auto") else "assisted",
            "items": export_items,
        }
        json_bytes = json.dumps(payload, indent=2).encode("utf-8")

        m1, m2, m3 = st.columns(3)
        m1.metric("Included items", len(export_items))
        m2.metric("Packages requested", sum(item["packages"] for item in export_items))
        m3.metric("Mode", "Auto" if payload["mode"] == "auto" else "Assisted")

        st.download_button(
            "Download walmart_cart.json",
            data=json_bytes,
            file_name="walmart_cart.json",
            mime="application/json",
            type="primary",
            use_container_width=True,
        )

        with st.expander("Preview export"):
            st.json(payload)

        st.markdown(
            """
            **Next:**
            1. Load the included Chrome extension using Chrome's **Load unpacked** option.
            2. Open Walmart, sign in, and confirm your local pickup store.
            3. Open the extension, import `walmart_cart.json`, and start the run.
            4. Review the final Walmart cart before selecting pickup and paying.
            """
        )
