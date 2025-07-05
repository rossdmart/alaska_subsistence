import os
import io
import re
from datetime import datetime

import boto3
import ijson
import streamlit as st

# 1) S3 configuration (set these as Render env vars)
AWS_REGION = os.getenv("AWS_REGION", "us-east-2")
S3_BUCKET  = os.getenv("S3_BUCKET")
if not S3_BUCKET:
    st.error("Please set the S3_BUCKET environment variable.")
    st.stop()

s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

# 2) Prefixes for JSON (search) and TXT (link) folders in your bucket
JSON_PREFIX  = {"EIRAC": "Embedded_EIRAC", "WIRAC": "Embedded_WIRAC"}
TXT_PREFIX   = {"EIRAC": "Cleaned_EIRAC",   "WIRAC": "Cleaned_WIRAC"}

# 3) Region → file-name prefix mapping
FILE_PREFIX  = {"EIRAC": "R9", "WIRAC": "R6"}

# 4) Base URL for your public .txt files
STATIC_BASE = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com"

# 5) Customize these!
WELCOME_MESSAGE = """\
**Welcome! This webpage runs keyword searches of Alaska Western and Eastern Interior Regional Advisory Council meeting transcripts.**

These meetings have been hosted biannually from 1993-today by The Federal Office of Subsistence Management. Each Regional Advisory Council convenes to talk about matters of importance to federal subsistence management policy in Alaska.

Here's how it works: type in your search keyword, and click run search. A search usually takes around 5 minutes. Don't let your computer sleep, or it may halt the search!

The search results only fetch the uninterrupted speaker turn that contains the keyword. So you won't get a back-and-forth conversation. If you want the full conversation and discussion context, click the document hyperlink to view the raw text file from from that specific date. Then simply copy and paste the search result into a Command F search of the text file to read more thoroughly.

Please give me feedback on this tool! **Email me at ross.martin@yale.edu with questions comments, or just to connect.** I developed it as part of my PhD research-- I plan to update and improve it over time.
"""
DEFAULT_KEYWORD = "What do you want to find?"

# 6) Streamlit page setup
st.set_page_config(page_title="Subsistence Transcript Search", layout="wide")
st.info(WELCOME_MESSAGE)
st.title("Subsistence Transcript Search")

region     = st.sidebar.selectbox("Region", list(JSON_PREFIX.keys()))
keyword    = st.sidebar.text_input("Keyword", DEFAULT_KEYWORD)
start_year = st.sidebar.number_input("Start Year", 1900, 2100, 1993)
end_year   = st.sidebar.number_input("End Year",   1900, 2100, 2024)
run_search = st.sidebar.button("Run Search")

# 7) List JSON keys + parse dates (cached)
@st.cache_data(show_spinner=False)
def list_json_keys(region_key):
    prefix = JSON_PREFIX[region_key] + "/"
    resp   = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=prefix)
    items  = resp.get("Contents", []) or []
    parsed = []
    for obj in items:
        key = obj["Key"]
        if key.lower().endswith(".json"):
            fname    = key.rsplit("/", 1)[-1]
            date_str = fname.split("_")[1].split(".")[0]
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                dt = None
            parsed.append((key, dt))
    return parsed

# 8) Perform search when button clicked
if run_search:
    all_json = list_json_keys(region)
    filtered = [(k, d) for k, d in all_json if d and start_year <= d.year <= end_year]
    st.sidebar.markdown(f"• {len(filtered)} transcript files in {start_year}–{end_year}")
    if not filtered:
        st.warning("No transcripts found in that date range.")
        st.stop()

    results = []
    with st.spinner("Searching transcripts…"):
        progress = st.sidebar.progress(0)
        for i, (json_key, _) in enumerate(filtered):
            obj = s3.get_object(Bucket=S3_BUCKET, Key=json_key)
            byts = obj["Body"].read()
            for rec in ijson.items(io.BytesIO(byts), "item"):
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
            txt_key  = f"{TXT_PREFIX[region]}/{FILE_PREFIX[region]}_{date_str}.txt"
            txt_url  = f"{STATIC_BASE}/{txt_key}"
            link_text = f"📄 View full transcript ({date_str}) — {speaker}"
            st.markdown(f"[**{link_text}**]({txt_url})")
            st.write(r["Text"])
            st.markdown("---")
