import streamlit as st
import pandas as pd
from data_loader import build_index, normalize_phone

st.set_page_config(page_title="Customer Lookup", page_icon="🔎", layout="centered")

st.title("🔎 Customer Lookup")
st.caption("Search any customer by phone number across all your Google Sheets.")

if "index" not in st.session_state:
    st.session_state.index = None
    st.session_state.errors = []
    st.session_state.stats = None

col1, col2 = st.columns([1, 3])
with col1:
    refresh = st.button("🔄 Refresh data", use_container_width=True)

if refresh or st.session_state.index is None:
    status = st.empty()
    progress_log = []

    def progress_callback(msg):
        progress_log.append(msg)
        status.info(msg)

    with st.spinner("Pulling data from all registered sheets..."):
        index, errors, stats = build_index(progress_callback=progress_callback)
        st.session_state.index = index
        st.session_state.errors = errors
        st.session_state.stats = stats
    status.empty()

stats = st.session_state.stats
if stats:
    st.success(
        f"Indexed {stats['sheets_registered']} sheet(s), "
        f"{stats['tabs_read']} tab(s), "
        f"{stats['rows_scanned']} row(s), "
        f"{stats['unique_phone_numbers']} unique phone number(s)."
    )

if st.session_state.errors:
    with st.expander(f"⚠️ {len(st.session_state.errors)} sheet(s)/tab(s) had issues"):
        for name, msg in st.session_state.errors:
            st.write(f"**{name}**: {msg}")

st.divider()

query = st.text_input("Enter phone number", placeholder="e.g. 9876543210 or +91 98765 43210")

if query:
    norm = normalize_phone(query)
    if not norm:
        st.warning("That doesn't look like a valid phone number. Try entering just the 10-digit number.")
    else:
        matches = st.session_state.index.get(norm, []) if st.session_state.index else []
        if not matches:
            st.error(f"No customer found with phone number matching {query}.")
        else:
            st.success(f"Found {len(matches)} match(es) for {query}:")
            for i, m in enumerate(matches, start=1):
                st.subheader(f"Match {i}: {m['sheet_name']} → tab '{m['tab_name']}' (row {m['row_number']})")
                row_df = pd.DataFrame(list(m["row_data"].items()), columns=["Field", "Value"])
                st.table(row_df)
