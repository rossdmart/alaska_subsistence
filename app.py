import os
import io
import re
from datetime import datetime
from pathlib import Path

import dropbox
import ijson
import streamlit as st

REGION_DBX = {
    "EIRAC": "/WIRAC_EIRAC_JSON/Embedded_EIRAC",
    "WIRAC": "/WIRAC_EIRAC_JSON/Embedded_WIRAC"
}

st.set_page_config(page_title="Subsistence Transcript Search", layout="wide")
st.title("Subsistence Transcript Search")

region = st.sidebar.selectbox("Region", list(REGION_DBX))
keyword = st.sidebar.text_input("Keyword", "fecundity")
start_year = st.sidebar.number_input("Start Year", 1900, 2100, 1993)
end_year = st.sidebar.number_input("End Year",   1900, 2100, 2024)
run_search = st.sidebar.button("Run Search")

token = os.getenv("DROPBOX_TOKEN")
if not token:
    st.error("Please set DROPBOX_TOKEN in your environment and restart.")
    st.stop()

dbx = dropbox.Dropbox(token)

@st.cache_data(show_spinner=False)
def list_files(region_key):
    entries = dbx.files_list_folder(REGION_DBX[region_key]).entries
    files = [e.path_lower for e in entries if hasattr(e, "path_lower") and e.name.lower().endswith(".json")]
    dates = []
    for p in files:
        fname = os.path.basename(p)
        ds = fname.split("_")[1].split(".")[0]
        try:
            dates.append(datetime.strptime(ds, "%Y-%m-%d"))
        except:
            dates.append(None)
    return list(zip(files, dates))

if run_search:
    files_with_dates = list_files(region)
    filtered = [(p, d) for p, d in files_with_dates if d and start_year <= d.year <= end_year]
    st.sidebar.markdown(f"• {len(filtered)} file(s) in {start_year}–{end_year}")
    if not filtered:
        st.warning("No transcripts found in that date range.")
        st.stop()
    results = []
    with st.spinner("Searching transcripts…"):
        progress = st.sidebar.progress(0)
        for i, (path, _) in enumerate(filtered):
            _, res = dbx.files_download(path)
            for rec in ijson.items(io.BytesIO(res.content), "item"):
                text = rec.get("text", "")
                if re.search(rf"{re.escape(keyword)}s?", text, re.IGNORECASE):
                    results.append({
                        "Date":    rec.get("date"),
                        "Speaker": rec.get("speaker"),
                        "Text":    text
                    })
            progress.progress(int((i + 1) / len(filtered) * 100))
    if not results:
        st.warning("No matches found.")
    else:
        for r in sorted(results, key=lambda x: x["Date"]):
            st.markdown(f"**{r['Date']} — {r['Speaker']}**")
            st.write(r["Text"])
            st.markdown("---")
