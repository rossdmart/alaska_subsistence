import os
import io
import re
from datetime import datetime

import dropbox
import ijson
import streamlit as st

# ── 1) Region → Dropbox JSON folder mapping ─────────────────────────────────────
REGION_DBX = {
    "EIRAC": "/WIRAC_EIRAC_JSON/Embedded_EIRAC",
    "WIRAC": "/WIRAC_EIRAC_JSON/Embedded_WIRAC"
}

# ── 2) Public shared-folder URLs for the raw .txt transcripts ───────────────────
PUBLIC_TXT_BASE = {
    "EIRAC": "https://www.dropbox.com/scl/fo/ek5u6cc4r3jrzd8p4gjx6/AIziFMTXCyKgHomJ55S2lRo?rlkey=3l74woavcoh9jm9foc07o6s1b&dl=0",
    "WIRAC": "https://www.dropbox.com/scl/fo/hfwhukvda06jt8bfyuqn0/AKW2A8eVU-_l1Y2mgioUA-Y?rlkey=0cek6v8ducllrpv2zpt6165hb&dl=0"
}

# ── 3) Customize your welcome message and default search term here ─────────────
WELCOME_MESSAGE = """\
**Welcome! This webpage runs keyword searches of Alaska Western and Eastern Interior Regional Advisory Council meeting transcripts!**


These meetings have been hosted biannually from 1993-today by The Federal Office of Subsistence Management. Each Regional advisory council convenes to talk about matters of importance to federal subsistence management policy in Alaska.
Here's how it works: type in your search keyword, and click run search. A search usually takes around 5 minutes. Don't let your computer sleep, or it may halt the search!
The search results only fetch the uninterrupted speaker turn that contains the keyword. So you won't get a back-and-forth conversation. If you want the full conversation and discussion context, click the document hyperlink to view the raw text file from from that specific date. Then simply copy and paste the search result into a Command F search of the text file to read more thoroughly.
Please give me feedback on this tool! **Email me at ross.martin@yale.edu with questions comments, or just to connect.** I developed it as part of my PhD research-- I plan to update and improve it over time. 

"""
DEFAULT_KEYWORD = "What do you want to find?"
# ────────────────────────────────────────────────────────────────────────────────

st.set_page_config(page_title="Subsistence Transcript Search", layout="wide")
st.info(WELCOME_MESSAGE)
st.title("Subsistence Transcript Search")

# ── 4) Sidebar controls ─────────────────────────────────────────────────────────
region     = st.sidebar.selectbox("Region", list(REGION_DBX))
keyword    = st.sidebar.text_input("Keyword", DEFAULT_KEYWORD)
start_year = st.sidebar.number_input("Start Year", 1900, 2100, 1993)
end_year   = st.sidebar.number_input("End Year",   1900, 2100, 2024)
run_search = st.sidebar.button("Run Search")

# ── 5) Dropbox client setup ─────────────────────────────────────────────────────
token = os.getenv("DROPBOX_TOKEN")
if not token:
    st.error("Please set DROPBOX_TOKEN in your environment and restart the app.")
    st.stop()
dbx = dropbox.Dropbox(token)

# ── 6) List JSON files + parse dates (cached) ──────────────────────────────────
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

# ── 7) Run search when button is clicked ────────────────────────────────────────
if run_search:
    try:
        files_with_dates = list_files(region)
    except Exception as e:
        st.error(f"Failed to list files from Dropbox: {e}")
        st.stop()

    # Filter by year range
    filtered = [
        (path, date) for path, date in files_with_dates
        if date and start_year <= date.year <= end_year
    ]
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
