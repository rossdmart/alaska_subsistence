import os
import io
import re
from datetime import datetime

import dropbox
import ijson
import streamlit as st

REGION_DBX = {
    "EIRAC": "/WIRAC_EIRAC_JSON/Embedded_EIRAC",
    "WIRAC": "/WIRAC_EIRAC_JSON/Embedded_WIRAC"
}

PUBLIC_TXT_BASE = {
    "EIRAC": "https://www.dropbox.com/scl/fo/ek5u6cc4r3jrzd8p4gjx6/AIziFMTXCyKgHomJ55S2lRo?rlkey=3l74woavcoh9jm9foc07o6s1b&st=f23yzzbh&dl=0",
    "WIRAC": "https://www.dropbox.com/scl/fo/hfwhukvda06jt8bfyuqn0/AKW2A8eVU-_l1Y2mgioUA-Y?rlkey=0cek6v8ducllrpv2zpt6165hb&st=kqwt0sgp&dl=0"
}

st.set_page_config(page_title="Subsistence Transcript Search", layout="wide")
st.info(
    "**Welcome to the Alaska Subsistence Transcript Search!**\n"
    "Use the controls on the left to select a region, keyword, and date range.\n"
    "Click Run Search to retrieve relevant speaker turns.\n"
    "Click the document icon link to view the full transcript file."
)
st.title("Subsistence Transcript Search")

region = st.sidebar.selectbox("Region", list(REGION_DBX))
keyword = st.sidebar.text_input("Keyword", "fecundity")
start_year = st.sidebar.number_input("Start Year", 1900, 2100, 1993)
end_year   = st.sidebar.number_input("End Year",   1900, 2100, 2024)
run_search = st.sidebar.button("Run Search")

token = os.getenv("DROPBOX_TOKEN")
if not token:
    st.error("Please set DROPBOX_TOKEN in your environment and restart the app.")
    st.stop()

dbx = dropbox.Dropbox(token)

@st.cache_data(show_spinner=False)
def list_files(region_key):
    entries = dbx.files_list_folder(REGION_DBX[region_key]).entries
    parsed = []
    for e in entries:
        if hasattr(e, "path_lower") and e.name.lower().endswith(".json"):
            p = e.path_lower
            ds = os.path.basename(p).split("_")[1].split(".")[0]
            try:
                date_obj = datetime.strptime(ds, "%Y-%m-%d")
            except ValueError:
                date_obj = None
            parsed.append((p, date_obj))
    return parsed

if run_search:
    try:
        files_with_dates = list_files(region)
    except Exception as e:
        st.error(f"Failed to list files from Dropbox: {e}")
        st.stop()

    filtered = [(p, d) for p, d in files_with_dates if d and start_year <= d.year <= end_year]
    st.sidebar.markdown(f"• {len(filtered)} file(s) in {start_year}–{end_year}")
    if not filtered:
        st.warning("No transcripts found in that date range.")
        st.stop()

    results = []
    with st.spinner("Searching transcripts…"):
        progress = st.sidebar.progress(0)
        for i, (path, _) in enumerate(filtered):
            try:
                _, res = dbx.files_download(path)
            except Exception as e:
                st.error(f"Connection failed downloading {os.path.basename(path)}: {e}")
                st.stop()
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
            date_str = r["Date"]
            speaker  = r["Speaker"]
            txt_url   = f"{PUBLIC_TXT_BASE[region]}/{region}_{date_str}.txt?raw=1"
            link_text = f"📄 View full transcript ({date_str}) — {speaker}"
            st.markdown(f"[**{link_text}**]({txt_url})")
            st.write(r["Text"])
            st.markdown("---")
