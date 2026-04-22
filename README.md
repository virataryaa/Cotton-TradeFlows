# Cotton Trade Flows

Streamlit dashboard for TDM cotton export flows.

## App

Main file for Streamlit Cloud:

```text
Dashboard/app.py
```

## Data

The dashboard reads:

```text
Database/tdm_cotton_exports.parquet
```

Current scope:

| Field | Scope |
|---|---|
| Flow | Exports |
| Reporters | China, United States, Brazil |
| HS | Chapter 52 cotton headings |

## Local Run

```bash
pip install -r requirements.txt
streamlit run Dashboard/app.py
```

## Refresh Data

Set your TDM API key, then run:

```bash
set TDM_API_KEY=your_key_here
python Code/cotton_exports_ingest.py --full
```
