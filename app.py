import base64
import json
import html
import re
import unicodedata
import time
from io import BytesIO
from urllib.parse import quote
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

APP_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="Tooling Control Tower",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# GOOGLE SHEETS PODEŠAVANJA
# =========================================================
SHEET_ID_UDARCI = "1gIzT5wNK2WXAAZ1iP34wCRaNYO4ej4CFjHWRiKvwUUo"
SHEET_ID_KVAROVI = "156nVcAzTJaAAZ5aKmlvKfaHLm4tIqkIq6U7RPRFmKOU"
GID_KVAROVI = "459292885"
SHEET_ID_DELOVI = "1g93otM7o8MalACWs1VpQT5mUtmDBr6A8L4i3VGa4agY"
SHEET_DELOVI = "BAZA A"
SHEET_DOKUMENTACIJA = "DOKUMENTACIJA"

EXCEL_URL_UDARCI = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_UDARCI}/export?format=xlsx"
CSV_URL_KVAROVI = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_KVAROVI}/gviz/tq?tqx=out:csv&gid={GID_KVAROVI}"
EXCEL_URL_KVAROVI = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_KVAROVI}/export?format=xlsx"
CSV_URL_DELOVI = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_DELOVI}/gviz/tq?tqx=out:csv&sheet={quote(SHEET_DELOVI)}"
EXCEL_URL_DELOVI = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_DELOVI}/export?format=xlsx"

START_SHEET_UDARCI = "09.2024"
CACHE_TTL = 900

# Preventivno održavanje
TOOL_LIFE_PUNCHES = 150_000_000
PREVENTIVE_LIMIT_20 = TOOL_LIFE_PUNCHES * 0.20
PREVENTIVE_LIMIT_80 = TOOL_LIFE_PUNCHES * 0.80
PREVENTIVE_INTERVAL_FIRST = 2_500_000
PREVENTIVE_INTERVAL_MIDDLE = 2_000_000
PREVENTIVE_INTERVAL_LAST = 1_500_000
PREVENTIVE_WARNING_RATIO = 0.80
SHEET_PREVENTIVA_ISTORIJA = "PREVENTIVA_ISTORIJA"

# Apps Script URL za upis udaraca.
# Najbolje je da se čuva u config.json, da ga ne unosiš svaki put.
APPS_SCRIPT_URL_DEFAULT = ""
CONFIG_FILE = APP_DIR / "config.json"

# Praćenje smena za MTBF (opening / vreme rada alata).
# Jedna smena traje 410 minuta (konstanta). Dani uneti pre nego što je počelo
# unošenje smena vode se kao 2 smene.
SMENE_FILE = APP_DIR / "smene.json"
SMENA_MINUTA = 410
PODRAZUMEVANE_SMENE = 2


# =========================================================
# STIL I POZADINA
# =========================================================
def set_background(image_file: str):
    try:
        with open(image_file, "rb") as image:
            encoded = base64.b64encode(image.read()).decode()
        bg_css = f"""
        background-image:
            linear-gradient(rgba(4, 9, 16, 0.82), rgba(4, 9, 16, 0.90)),
            url('data:image/png;base64,{encoded}');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        """
    except Exception:
        bg_css = "background: radial-gradient(circle at 15% 0%, #101d30 0%, #070c14 55%, #050810 100%);"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600&display=swap');

        :root {{
            --bg-0: #070c14;
            --bg-1: #0c1420;
            --panel: rgba(21, 30, 46, 0.82);
            --panel-soft: rgba(21, 30, 46, 0.55);
            --panel-solid: #131d2e;
            --border: rgba(126, 170, 224, 0.20);
            --border-strong: rgba(126, 170, 224, 0.38);
            --text-hi: #f4f8fd;
            --text-md: #c3d0e3;
            --text-lo: #93a1b8;
            --accent: #29d3c8;
            --accent-soft: rgba(41, 211, 200, 0.16);
            --accent-line: rgba(41, 211, 200, 0.45);
            --blue: #4fa8f5;
            --amber: #f5b942;
            --red: #f2607a;
            --green: #3ed598;
            --radius-lg: 16px;
            --radius-md: 12px;
            --shadow: 0 10px 30px rgba(0,0,0,0.38);
        }}

        html, body, [class*="css"] {{ font-family: 'Inter', -apple-system, sans-serif; }}

        .stApp {{ {bg_css} }}
        [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
        [data-testid="stAppViewContainer"] {{ font-family: 'Inter', sans-serif; }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, #0a121e 0%, #0c1522 100%);
            border-right: 1px solid var(--border);
        }}
        [data-testid="stSidebar"] > div:first-child {{ padding-top: 1.2rem; }}

        .block-container {{
            padding-top: 1.2rem;
            padding-bottom: 2.5rem;
            max-width: 1880px;
        }}

        /* ================= HEADER ================= */
        .top-header {{
            display: grid;
            grid-template-columns: 250px 1fr 250px;
            align-items: stretch;
            gap: 16px;
            margin-bottom: 22px;
        }}
        .company-logo-box {{
            min-height: 72px;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            padding: 8px 16px;
            background: var(--panel-soft);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow);
        }}
        .company-logo-box img {{
            max-height: 52px;
            max-width: 205px;
            object-fit: contain;
        }}
        .logo-missing {{
            color: var(--text-lo);
            font-size: 12px;
            line-height: 1.3;
        }}
        .tower-title-box {{
            text-align: center;
            padding: 14px 26px;
            background: linear-gradient(135deg, rgba(15, 26, 42, 0.9), rgba(19, 34, 52, 0.82));
            border: 1px solid var(--accent-line);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow), inset 0 0 30px rgba(41, 211, 200, 0.06);
            position: relative;
            overflow: hidden;
        }}
        .tower-title-box::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 2px;
            background: linear-gradient(90deg, transparent, var(--accent), transparent);
        }}
        .tower-title {{
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            font-size: 34px;
            font-weight: 700;
            color: var(--text-hi);
            letter-spacing: 0.2px;
            line-height: 1.15;
        }}
        .tower-subtitle {{
            color: var(--text-md);
            font-size: 13.5px;
            margin-top: 5px;
            letter-spacing: 0.1px;
        }}
        .creator-box {{
            min-height: 72px;
            text-align: right;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 10px 16px;
            background: var(--panel-soft);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            color: var(--text-md);
            font-size: 11.5px;
            line-height: 1.4;
        }}
        .creator-name {{
            color: var(--text-hi);
            font-weight: 700;
            font-size: 13px;
        }}
        @media (max-width: 1100px) {{
            .top-header {{ grid-template-columns: 1fr; }}
            .company-logo-box, .creator-box {{ justify-content: center; text-align: center; }}
            .tower-title {{ font-size: 28px; }}
        }}

        /* ================= CARDS / PANELS ================= */
        .section-card {{
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 20px 20px 16px 20px;
            margin-bottom: 18px;
            box-shadow: var(--shadow);
        }}
        .section-card .stSubheader, .section-card h3 {{ margin-top: 0; }}

        .kpi-card {{
            background: linear-gradient(160deg, rgba(22, 34, 52, 0.95), rgba(16, 25, 40, 0.92));
            border: 1px solid var(--border);
            border-left: 3px solid var(--accent);
            border-radius: var(--radius-md);
            padding: 14px 16px;
            min-height: 96px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.28);
            transition: border-color .15s ease;
        }}
        .kpi-title {{
            color: var(--text-lo);
            font-size: 11.5px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: .6px;
        }}
        .kpi-value {{
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            color: var(--text-hi);
            font-size: 26px;
            font-weight: 700;
            margin-top: 4px;
            line-height: 1.2;
        }}
        .kpi-note {{
            color: var(--text-lo);
            font-size: 11.5px;
            margin-top: 6px;
        }}

        .kanban-col {{
            background: var(--panel-soft);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: 12px;
            min-height: 520px;
        }}
        .kanban-title {{
            font-size: 17px;
            font-weight: 700;
            margin-bottom: 12px;
            color: var(--text-hi);
        }}
        .kanban-item {{
            background: rgba(255,255,255,0.045);
            border: 1px solid rgba(255,255,255,0.09);
            border-radius: var(--radius-md);
            padding: 12px 14px;
            margin-bottom: 10px;
            transition: border-color .15s ease, background .15s ease;
        }}
        .kanban-item:hover {{
            border-color: var(--accent-line);
            background: rgba(255,255,255,0.07);
        }}
        .kanban-item-title {{
            color: var(--text-hi);
            font-weight: 700;
            font-size: 13.5px;
        }}
        .kanban-item-meta {{
            color: var(--text-md);
            font-size: 12px;
            margin-top: 4px;
            line-height: 1.4;
        }}

        /* ================= TYPOGRAPHY ================= */
        h1, h2, h3, h4, h5, h6 {{
            color: var(--text-hi) !important;
            font-family: 'Space Grotesk', 'Inter', sans-serif !important;
            font-weight: 700 !important;
            letter-spacing: 0.1px;
        }}
        [data-testid="stMarkdownContainer"] h3 {{
            font-size: 19px !important;
            margin-bottom: 10px !important;
        }}
        p, label, span, div, .stMarkdown, .stText, .stCaption {{ color: var(--text-md); }}
        [data-testid="stCaptionContainer"] {{ color: var(--text-lo) !important; font-size: 12.5px !important; }}
        [data-testid="stWidgetLabel"] p {{ color: var(--text-hi) !important; font-weight: 600 !important; font-size: 13px; }}
        [data-testid="stSidebar"] * {{ color: var(--text-md) !important; }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: var(--text-hi) !important; }}

        /* ================= TABS ================= */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 8px;
            border-bottom: 1px solid var(--border);
            background: transparent;
            padding: 4px 2px 10px 2px;
            flex-wrap: wrap;
        }}
        .stTabs [data-baseweb="tab"] {{
            color: var(--text-md) !important;
            font-weight: 600 !important;
            font-size: 14px !important;
            padding: 11px 20px !important;
            border-radius: var(--radius-md) !important;
            background: var(--panel-soft) !important;
            border: 1px solid var(--border) !important;
            box-shadow: 0 4px 14px rgba(0,0,0,0.22);
            transition: transform .12s ease, box-shadow .12s ease, border-color .12s ease;
        }}
        .stTabs [data-baseweb="tab"] p {{ font-size: 14px !important; }}
        .stTabs [data-baseweb="tab"]:hover {{
            color: var(--text-hi) !important;
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.32);
        }}
        .stTabs [aria-selected="true"] {{
            color: var(--text-hi) !important;
            font-weight: 700 !important;
            transform: translateY(-2px);
            box-shadow: 0 10px 24px rgba(0,0,0,0.4);
        }}
        .stTabs [data-baseweb="tab-highlight"] {{ background-color: transparent !important; }}
        .stTabs [data-baseweb="tab-border"] {{ background-color: transparent !important; }}

        /* Svaki tab ima svoju nijansu akcentne boje (obojen okvir + naglašeno kad je aktivan) */
        .stTabs [data-baseweb="tab-list"] button:nth-child(1)  {{ border-top: 2px solid #29d3c8; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(2)  {{ border-top: 2px solid #4fa8f5; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(3)  {{ border-top: 2px solid #f5b942; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(4)  {{ border-top: 2px solid #a78bfa; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(5)  {{ border-top: 2px solid #f2607a; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(6)  {{ border-top: 2px solid #3ed598; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(7)  {{ border-top: 2px solid #f0985c; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(8)  {{ border-top: 2px solid #ec6fb0; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(9)  {{ border-top: 2px solid #7c8cf8; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(10) {{ border-top: 2px solid #38bdf8; }}
        .stTabs [data-baseweb="tab-list"] button:nth-child(11) {{ border-top: 2px solid #94a3b8; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(1)  {{ background: linear-gradient(180deg, rgba(41,211,200,0.22), var(--panel-soft)) !important; border-color: rgba(41,211,200,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(2)  {{ background: linear-gradient(180deg, rgba(79,168,245,0.22), var(--panel-soft)) !important; border-color: rgba(79,168,245,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(3)  {{ background: linear-gradient(180deg, rgba(245,185,66,0.22), var(--panel-soft)) !important; border-color: rgba(245,185,66,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(4)  {{ background: linear-gradient(180deg, rgba(167,139,250,0.22), var(--panel-soft)) !important; border-color: rgba(167,139,250,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(5)  {{ background: linear-gradient(180deg, rgba(242,96,122,0.22), var(--panel-soft)) !important; border-color: rgba(242,96,122,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(6)  {{ background: linear-gradient(180deg, rgba(62,213,152,0.22), var(--panel-soft)) !important; border-color: rgba(62,213,152,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(7)  {{ background: linear-gradient(180deg, rgba(240,152,92,0.22), var(--panel-soft)) !important; border-color: rgba(240,152,92,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(8)  {{ background: linear-gradient(180deg, rgba(236,111,176,0.22), var(--panel-soft)) !important; border-color: rgba(236,111,176,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(9)  {{ background: linear-gradient(180deg, rgba(124,140,248,0.22), var(--panel-soft)) !important; border-color: rgba(124,140,248,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(10) {{ background: linear-gradient(180deg, rgba(56,189,248,0.22), var(--panel-soft)) !important; border-color: rgba(56,189,248,0.55) !important; }}
        .stTabs [data-baseweb="tab-list"] button[aria-selected="true"]:nth-child(11) {{ background: linear-gradient(180deg, rgba(148,163,184,0.22), var(--panel-soft)) !important; border-color: rgba(148,163,184,0.55) !important; }}

        /* Svaki sadržaj taba ima suptilno drugačiju nijansu pozadine */
        .stTabs [data-baseweb="tab-panel"] {{
            border-radius: var(--radius-lg);
            padding: 18px 2px 4px 2px;
        }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(1)  {{ background: radial-gradient(circle at 0% 0%, rgba(41,211,200,0.055), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(2)  {{ background: radial-gradient(circle at 0% 0%, rgba(79,168,245,0.055), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(3)  {{ background: radial-gradient(circle at 0% 0%, rgba(245,185,66,0.05), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(4)  {{ background: radial-gradient(circle at 0% 0%, rgba(167,139,250,0.055), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(5)  {{ background: radial-gradient(circle at 0% 0%, rgba(242,96,122,0.05), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(6)  {{ background: radial-gradient(circle at 0% 0%, rgba(62,213,152,0.055), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(7)  {{ background: radial-gradient(circle at 0% 0%, rgba(240,152,92,0.05), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(8)  {{ background: radial-gradient(circle at 0% 0%, rgba(236,111,176,0.05), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(9)  {{ background: radial-gradient(circle at 0% 0%, rgba(124,140,248,0.055), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(10) {{ background: radial-gradient(circle at 0% 0%, rgba(56,189,248,0.055), transparent 55%); }}
        .stTabs [data-baseweb="tab-panel"]:nth-of-type(11) {{ background: radial-gradient(circle at 0% 0%, rgba(148,163,184,0.05), transparent 55%); }}

        /* Alarm indikator u zaglavlju (trougao sa uzvičnikom) */
        [data-testid="stPopover"] > button {{
            position: relative;
            width: 54px;
            height: 54px;
            min-width: 54px;
            padding: 0 !important;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px !important;
            line-height: 1 !important;
            background: linear-gradient(160deg, rgba(245,185,66,0.20), rgba(245,185,66,0.06)) !important;
            border: 1px solid rgba(245,185,66,0.45) !important;
            border-radius: 12px !important;
            box-shadow: 0 6px 18px rgba(0,0,0,0.30);
        }}
        [data-testid="stPopover"] > button:hover {{
            border-color: rgba(245,185,66,0.75) !important;
            box-shadow: 0 0 0 3px rgba(245,185,66,0.16), 0 6px 18px rgba(0,0,0,0.30);
        }}
        [data-testid="stPopover"] > button p {{ font-size: 24px !important; margin: 0 !important; }}


        .stButton > button, .stDownloadButton > button, .stLinkButton > a {{
            background: linear-gradient(135deg, rgba(41,211,200,0.16), rgba(41,211,200,0.08));
            border: 1px solid var(--accent-line);
            color: var(--text-hi);
            font-weight: 600;
            border-radius: 10px;
            transition: all .15s ease;
        }}
        .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {{
            border-color: var(--accent);
            background: linear-gradient(135deg, rgba(41,211,200,0.28), rgba(41,211,200,0.14));
            color: #ffffff;
        }}
        .stButton > button[kind="primary"] {{
            background: var(--accent);
            color: #06201d;
            border: 1px solid var(--accent);
        }}

        /* ================= DROPDOWNS / INPUTS ================= */
        [data-baseweb="select"] > div, .stTextInput input, .stNumberInput input, .stDateInput input {{
            background: var(--panel-solid) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            color: var(--text-hi) !important;
        }}
        [data-baseweb="select"] > div:hover, .stTextInput input:hover, .stDateInput input:hover {{
            border-color: var(--border-strong) !important;
        }}
        [data-baseweb="select"] span, [data-baseweb="select"] div {{ color: var(--text-hi) !important; }}
        input::placeholder, textarea::placeholder {{ color: var(--text-lo) !important; opacity: 1; }}

        /* Otvoreni padajući meni (popover/listbox) */
        [data-baseweb="popover"] [data-baseweb="menu"], [role="listbox"] {{
            background: var(--panel-solid) !important;
            border: 1px solid var(--border-strong) !important;
            border-radius: 10px !important;
            box-shadow: 0 14px 34px rgba(0,0,0,0.5) !important;
        }}
        [data-baseweb="popover"] li, [role="option"] {{
            color: var(--text-md) !important;
            font-size: 13.5px !important;
        }}
        [role="option"]:hover, [data-baseweb="popover"] li:hover {{
            background: var(--accent-soft) !important;
            color: var(--text-hi) !important;
        }}
        [aria-selected="true"][role="option"] {{
            background: var(--accent-soft) !important;
            color: var(--accent) !important;
        }}

        /* Multiselect čipovi */
        [data-baseweb="tag"] {{
            background: var(--accent-soft) !important;
            border: 1px solid var(--accent-line) !important;
            border-radius: 8px !important;
        }}
        [data-baseweb="tag"] span {{ color: var(--text-hi) !important; }}

        /* Expander */
        [data-testid="stExpander"] {{
            background: var(--panel-soft);
            border: 1px solid var(--border) !important;
            border-radius: var(--radius-md) !important;
            overflow: hidden;
        }}
        [data-testid="stExpander"] summary {{
            color: var(--text-hi) !important;
            font-weight: 600 !important;
        }}

        /* Alert boxes */
        .stAlert, .stInfo, .stWarning, .stSuccess, .stError {{ color: var(--text-hi) !important; border-radius: var(--radius-md) !important; }}

        /* Slideri i checkbox akcenat */
        [data-baseweb="slider"] div[role="slider"] {{ background-color: var(--accent) !important; }}
        .stCheckbox [data-baseweb="checkbox"] svg {{ fill: var(--accent) !important; }}

        /* Scrollbar */
        ::-webkit-scrollbar {{ width: 9px; height: 9px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: rgba(126, 170, 224, 0.35); border-radius: 8px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: rgba(126, 170, 224, 0.55); }}

        /* ================= TABELE ================= */
        [data-testid="stDataFrame"] {{
            background: var(--panel-solid) !important;
            border: 1px solid var(--border) !important;
            border-radius: var(--radius-md) !important;
            overflow: hidden !important;
        }}
        [data-testid="stDataFrame"] div {{ color: var(--text-hi) !important; font-size: 13px !important; }}
        [data-testid="stDataFrame"] canvas {{ filter: brightness(0.9) contrast(1.12); }}


        /* ================= FIXED LEFT NAVIGATION ================= */
        [data-testid="stSidebar"] {{
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            transform: translateX(0) !important;
            left: 0 !important;
            min-width: 255px !important;
            max-width: 255px !important;
            width: 255px !important;
            box-shadow: 12px 0 34px rgba(0,0,0,0.28);
            z-index: 999 !important;
        }}
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebar"] > div:first-child,
        [data-testid="stSidebarContent"],
        section[data-testid="stSidebar"] > div {{
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            transform: none !important;
            left: 0 !important;
            width: 255px !important;
            min-width: 255px !important;
        }}
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
            visibility: visible !important;
            opacity: 1 !important;
        }}
        [data-testid="stSidebarCollapseButton"],
        [data-testid="collapsedControl"],
        button[kind="headerNoPadding"] {{
            display: none !important;
        }}
        [data-testid="stSidebar"] [data-testid="stRadio"] > div {{
            gap: 7px !important;
        }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label {{
            background: rgba(17, 29, 46, 0.72);
            border: 1px solid rgba(126, 170, 224, 0.13);
            border-radius: 10px;
            padding: 9px 10px !important;
            margin: 0 !important;
            transition: all .15s ease;
            cursor: pointer;
        }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{
            background: rgba(41, 211, 200, 0.10);
            border-color: rgba(41, 211, 200, 0.35);
            transform: translateX(3px);
        }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
            background: linear-gradient(90deg, rgba(41,211,200,0.20), rgba(79,168,245,0.08));
            border-color: rgba(41,211,200,0.52);
            box-shadow: inset 3px 0 0 #29d3c8, 0 5px 16px rgba(0,0,0,0.25);
        }}
        [data-testid="stSidebar"] [data-testid="stRadio"] label p {{
            color: #dce8f8 !important;
            font-size: 13.5px !important;
            font-weight: 650 !important;
        }}
        .sidebar-brand {{
            border: 1px solid rgba(41,211,200,0.28);
            border-radius: 13px;
            padding: 13px 12px;
            margin: 2px 0 16px 0;
            background: linear-gradient(145deg, rgba(19,34,52,.95), rgba(10,19,31,.92));
            box-shadow: 0 9px 24px rgba(0,0,0,.28);
        }}
        .sidebar-brand-title {{
            color: #f5f9ff;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 16px;
            line-height: 1.2;
        }}
        .sidebar-brand-subtitle {{
            color: #8fa5bf;
            font-size: 10.5px;
            margin-top: 5px;
            text-transform: uppercase;
            letter-spacing: .7px;
        }}

        /* ================= ROBUST CUSTOM LEFT NAVIGATION ================= */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{
            display: none !important;
        }}
        /* Glavni sadržaj se fizički pomera desno od fiksnog menija.
           Koristimo aktuelne Streamlit data-testid selektore, jer .main
           više nije pouzdan u novijim verzijama Streamlit-a. */
        :root {{ --left-nav-width: 280px; }}
        .stApp {{
            overflow-x: hidden !important;
        }}
        [data-testid="stAppViewContainer"] {{
            box-sizing: border-box !important;
            padding-left: var(--left-nav-width) !important;
            width: 100% !important;
            max-width: 100% !important;
        }}
        [data-testid="stMain"],
        section[data-testid="stMain"],
        .stMain {{
            box-sizing: border-box !important;
            width: 100% !important;
            max-width: 100% !important;
            margin-left: 0 !important;
            overflow-x: hidden !important;
        }}
        [data-testid="stMainBlockContainer"],
        .stMainBlockContainer,
        .block-container {{
            box-sizing: border-box !important;
            width: 100% !important;
            max-width: none !important;
            margin-left: 0 !important;
            margin-right: 0 !important;
            padding-left: 1.45rem !important;
            padding-right: 1.45rem !important;
        }}
        .custom-left-nav {{
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            width: var(--left-nav-width);
            box-sizing: border-box;
            z-index: 100000;
            padding: 22px 14px 18px 14px;
            background: linear-gradient(180deg, rgba(7,14,24,.985) 0%, rgba(10,20,33,.985) 100%);
            border-right: 1px solid rgba(126,170,224,.22);
            box-shadow: 12px 0 34px rgba(0,0,0,.34);
            overflow-y: auto;
            backdrop-filter: blur(14px);
        }}
        .custom-nav-brand {{
            border: 1px solid rgba(41,211,200,.30);
            border-radius: 14px;
            padding: 14px 13px;
            margin-bottom: 18px;
            background: linear-gradient(145deg, rgba(19,34,52,.96), rgba(10,19,31,.94));
            box-shadow: 0 9px 24px rgba(0,0,0,.30);
        }}
        .custom-nav-brand-title {{
            color: #f5f9ff;
            font-family: 'Space Grotesk', sans-serif;
            font-weight: 700;
            font-size: 16px;
            line-height: 1.2;
        }}
        .custom-nav-brand-subtitle {{
            color: #8fa5bf;
            font-size: 10px;
            margin-top: 5px;
            text-transform: uppercase;
            letter-spacing: .75px;
        }}
        .custom-nav-list {{
            display: flex;
            flex-direction: column;
            gap: 7px;
        }}
        .custom-nav-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            min-height: 43px;
            padding: 9px 11px;
            color: #dce8f8 !important;
            text-decoration: none !important;
            background: rgba(17,29,46,.72);
            border: 1px solid rgba(126,170,224,.13);
            border-radius: 10px;
            transition: all .15s ease;
            font-size: 13.5px;
            font-weight: 650;
        }}
        .custom-nav-item:hover {{
            color: #ffffff !important;
            background: rgba(41,211,200,.11);
            border-color: rgba(41,211,200,.38);
            transform: translateX(3px);
        }}
        .custom-nav-item.active {{
            background: linear-gradient(90deg, rgba(41,211,200,.22), rgba(79,168,245,.09));
            border-color: rgba(41,211,200,.56);
            box-shadow: inset 3px 0 0 #29d3c8, 0 5px 16px rgba(0,0,0,.28);
            color: #ffffff !important;
        }}
        .custom-nav-icon {{
            width: 22px;
            text-align: center;
            font-size: 16px;
            flex: 0 0 22px;
        }}
        .custom-nav-label {{
            white-space: nowrap;
        }}
        .custom-nav-footer {{
            margin-top: 18px;
            padding: 10px 4px 0 4px;
            border-top: 1px solid rgba(126,170,224,.14);
            color: #7588a3;
            font-size: 10.5px;
            line-height: 1.4;
        }}
        @media (max-width: 1180px) {{
            :root {{ --left-nav-width: 238px; }}
            .custom-nav-label {{ font-size: 12px; }}
            .custom-left-nav {{ padding-left: 10px; padding-right: 10px; }}
        }}
        @media (max-width: 820px) {{
            :root {{ --left-nav-width: 205px; }}
            .custom-nav-brand-title {{ font-size: 14px; }}
            .custom-nav-brand-subtitle {{ font-size: 9px; }}
            .custom-nav-item {{ padding-left: 8px; padding-right: 8px; gap: 6px; }}
            .custom-nav-label {{ font-size: 11px; }}
        }}

        /* ================= COMPACT TOP FILTER BAR ================= */
        .filter-summary-bar {{
            min-height: 46px;
            display: flex;
            align-items: center;
            gap: 20px;
            padding: 9px 16px;
            background: linear-gradient(90deg, rgba(16,27,44,.92), rgba(17,31,49,.76));
            border: 1px solid rgba(126,170,224,.20);
            border-radius: 12px;
            box-shadow: 0 6px 20px rgba(0,0,0,.24);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .filter-summary-item {{
            color: #aebed2;
            font-size: 12px;
        }}
        .filter-summary-item b {{
            color: #eef6ff;
            font-weight: 700;
        }}
        .active-page-strip {{
            margin: 4px 0 12px 0;
            color: #8fa5bf;
            font-size: 11px;
            letter-spacing: .55px;
            text-transform: uppercase;
        }}
        .active-page-strip b {{ color: #29d3c8; }}
        [data-testid="stPopover"] > button {{
            min-height: 46px !important;
            width: 100% !important;
            font-size: 13px !important;
            border-radius: 12px !important;
            background: linear-gradient(135deg, rgba(41,211,200,.18), rgba(79,168,245,.10)) !important;
            border: 1px solid rgba(41,211,200,.38) !important;
        }}
        [data-testid="stPopoverBody"] {{
            min-width: min(920px, 90vw) !important;
            background: #111c2d !important;
            border: 1px solid rgba(126,170,224,.28) !important;
            border-radius: 14px !important;
            box-shadow: 0 18px 46px rgba(0,0,0,.55) !important;
        }}

        /* Dashboard-like chart containers */
        [data-testid="stPlotlyChart"] {{
            background: linear-gradient(160deg, rgba(18,31,49,.84), rgba(11,20,33,.74));
            border: 1px solid rgba(126,170,224,.16);
            border-radius: 14px;
            padding: 6px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,.025), 0 8px 22px rgba(0,0,0,.24);
        }}



        /* =====================================================
           STITCH / OBSIDIAN COMMAND — FINAL VISUAL OVERRIDES
           Serbian labels and existing application logic remain unchanged.
        ====================================================== */
        :root {{
            --left-nav-width: 240px;
            --surface: #0f1419;
            --surface-lowest: #0a0e14;
            --surface-low: #181c22;
            --surface-container: #1c2026;
            --surface-high: #262a30;
            --surface-highest: #31353b;
            --on-surface: #dfe2ea;
            --on-surface-variant: #bfc7d4;
            --outline: #89919d;
            --outline-variant: #404752;
            --primary: #9ecaff;
            --primary-strong: #2196f3;
            --warning: #ffb77b;
            --danger: #ffb4ab;
            --success: #78dba9;
            --tech-radius: 4px;
        }}

        html, body, .stApp, [data-testid="stAppViewContainer"] {{
            background: var(--surface) !important;
            color: var(--on-surface) !important;
        }}
        .stApp {{
            background-image: none !important;
            overflow-x: hidden !important;
        }}
        [data-testid="stHeader"] {{
            background: rgba(15,20,25,.96) !important;
            border-bottom: 1px solid var(--outline-variant) !important;
        }}
        [data-testid="stToolbar"] {{ right: 10px !important; }}

        /* Main canvas begins after the 240px fixed navigation. */
        [data-testid="stAppViewContainer"] {{
            padding-left: var(--left-nav-width) !important;
            width: 100% !important;
            box-sizing: border-box !important;
        }}
        [data-testid="stMain"], section[data-testid="stMain"], .stMain {{
            margin-left: 0 !important;
            width: 100% !important;
            max-width: 100% !important;
            box-sizing: border-box !important;
            overflow-x: hidden !important;
        }}
        [data-testid="stMainBlockContainer"], .stMainBlockContainer, .block-container {{
            width: 100% !important;
            max-width: none !important;
            box-sizing: border-box !important;
            padding: 14px 14px 34px 14px !important;
            margin: 0 !important;
        }}

        /* Hide native sidebar; application uses its own fixed navigation. */
        [data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"] {{ display: none !important; }}

        /* Fixed left navigation, matching Stitch's mission-control layout. */
        .custom-left-nav {{
            position: fixed !important;
            inset: 0 auto 0 0 !important;
            width: var(--left-nav-width) !important;
            box-sizing: border-box !important;
            z-index: 100000 !important;
            padding: 0 !important;
            background: #0b1016 !important;
            border-right: 1px solid var(--outline-variant) !important;
            box-shadow: none !important;
            overflow-y: auto !important;
        }}
        .custom-nav-brand {{
            min-height: 82px !important;
            box-sizing: border-box !important;
            padding: 15px 16px 12px !important;
            margin: 0 !important;
            border: 0 !important;
            border-bottom: 1px solid var(--outline-variant) !important;
            border-radius: 0 !important;
            background: #0f1419 !important;
            box-shadow: none !important;
        }}
        .custom-nav-logo {{
            width: 150px;
            max-height: 34px;
            object-fit: contain;
            object-position: left center;
            display: block;
            margin-bottom: 8px;
        }}
        .custom-nav-brand-title {{
            color: var(--on-surface) !important;
            font-family: Inter, sans-serif !important;
            font-size: 17px !important;
            font-weight: 700 !important;
            letter-spacing: -.2px !important;
        }}
        .custom-nav-brand-subtitle {{
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 10px !important;
            text-transform: uppercase !important;
            letter-spacing: 1px !important;
            margin-top: 3px !important;
        }}
        .custom-nav-list {{
            display: flex !important;
            flex-direction: column !important;
            gap: 0 !important;
            padding: 10px 5px 78px !important;
        }}
        .custom-nav-item {{
            min-height: 46px !important;
            display: flex !important;
            align-items: center !important;
            gap: 12px !important;
            padding: 0 14px !important;
            margin: 0 !important;
            color: var(--on-surface-variant) !important;
            background: transparent !important;
            border: 0 !important;
            border-left: 4px solid transparent !important;
            border-radius: 0 !important;
            box-shadow: none !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 12px !important;
            font-weight: 500 !important;
            letter-spacing: .2px !important;
            text-decoration: none !important;
            transform: none !important;
        }}
        .custom-nav-item:hover {{
            color: var(--on-surface) !important;
            background: var(--surface-container) !important;
            border-left-color: var(--outline) !important;
            transform: none !important;
        }}
        .custom-nav-item.active {{
            color: var(--primary) !important;
            background: var(--surface-high) !important;
            border-left-color: var(--primary) !important;
            box-shadow: inset 0 0 16px rgba(158,202,255,.035) !important;
        }}
        .custom-nav-icon {{
            width: 24px !important;
            flex: 0 0 24px !important;
            font-size: 17px !important;
            text-align: center !important;
        }}
        .custom-nav-label {{ white-space: nowrap !important; }}
        .custom-nav-footer {{
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            width: var(--left-nav-width) !important;
            box-sizing: border-box !important;
            padding: 12px 16px !important;
            margin: 0 !important;
            background: var(--surface-lowest) !important;
            border-top: 1px solid var(--outline-variant) !important;
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 10px !important;
            text-transform: uppercase !important;
            letter-spacing: .7px !important;
        }}

        /* Compact top command header. */
        .tower-title-box {{
            min-height: 64px !important;
            box-sizing: border-box !important;
            display: flex !important;
            flex-direction: column !important;
            align-items: flex-start !important;
            justify-content: center !important;
            text-align: left !important;
            padding: 10px 16px !important;
            background: var(--surface-low) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            box-shadow: none !important;
        }}
        .tower-title-box::before {{ display: none !important; }}
        .tower-title {{
            font-family: Inter, sans-serif !important;
            font-size: 23px !important;
            font-weight: 700 !important;
            color: var(--on-surface) !important;
            line-height: 1.15 !important;
            letter-spacing: -.35px !important;
        }}
        .tower-subtitle {{
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 10.5px !important;
            line-height: 1.35 !important;
            margin-top: 4px !important;
            text-transform: uppercase !important;
            letter-spacing: .45px !important;
        }}
        .creator-box {{
            min-height: 64px !important;
            box-sizing: border-box !important;
            padding: 9px 12px !important;
            background: var(--surface-low) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 9px !important;
            text-transform: uppercase !important;
            letter-spacing: .5px !important;
            box-shadow: none !important;
        }}
        .creator-name {{
            color: var(--on-surface) !important;
            font-size: 11px !important;
            margin-top: 4px !important;
            text-transform: none !important;
            letter-spacing: 0 !important;
        }}
        .company-logo-box {{ display: none !important; }}

        /* Alert and refresh controls. */
        [data-testid="stPopover"] > button,
        .stButton > button,
        .stDownloadButton > button,
        .stLinkButton > a {{
            min-height: 40px !important;
            border-radius: var(--tech-radius) !important;
            background: var(--surface-high) !important;
            border: 1px solid var(--outline-variant) !important;
            color: var(--on-surface) !important;
            box-shadow: none !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 11px !important;
            font-weight: 600 !important;
        }}
        [data-testid="stPopover"] > button:hover,
        .stButton > button:hover,
        .stDownloadButton > button:hover,
        .stLinkButton > a:hover {{
            background: var(--surface-highest) !important;
            border-color: var(--primary) !important;
            color: var(--primary) !important;
        }}
        .stButton > button[kind="primary"] {{
            background: var(--primary-strong) !important;
            border-color: var(--primary-strong) !important;
            color: #fff !important;
        }}
        [data-testid="stPopoverBody"] {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            box-shadow: 0 18px 44px rgba(0,0,0,.55) !important;
        }}

        /* Filter command strip. */
        .filter-summary-bar {{
            min-height: 40px !important;
            box-sizing: border-box !important;
            padding: 7px 12px !important;
            gap: 22px !important;
            background: var(--surface-low) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            box-shadow: none !important;
        }}
        .filter-summary-item {{
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 10.5px !important;
            text-transform: uppercase !important;
            letter-spacing: .35px !important;
        }}
        .filter-summary-item b {{ color: var(--primary) !important; }}
        .active-page-strip {{
            margin: 7px 0 9px !important;
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 9.5px !important;
            letter-spacing: .8px !important;
        }}
        .active-page-strip b {{ color: var(--primary) !important; }}

        /* Precision-oriented cards and panels. */
        .section-card {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            padding: 14px !important;
            margin-bottom: 12px !important;
            box-shadow: none !important;
        }}
        .kpi-card {{
            position: relative !important;
            min-height: 112px !important;
            box-sizing: border-box !important;
            padding: 15px 14px 12px !important;
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-top: 3px solid var(--primary) !important;
            border-left: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            box-shadow: 0 0 14px rgba(33,150,243,.06) !important;
        }}
        .kpi-title {{
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 10px !important;
            font-weight: 600 !important;
            text-transform: uppercase !important;
            letter-spacing: .55px !important;
        }}
        .kpi-value {{
            color: var(--on-surface) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 25px !important;
            font-weight: 700 !important;
            line-height: 1.25 !important;
            margin-top: 8px !important;
        }}
        .kpi-note {{
            color: var(--on-surface-variant) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 9.5px !important;
            margin-top: 7px !important;
        }}
        .kanban-col {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
        }}
        .kanban-item {{
            background: var(--surface-high) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
        }}
        .kanban-item:hover {{ border-color: var(--primary) !important; }}
        .kanban-item-title {{ color: var(--on-surface) !important; }}
        .kanban-item-meta {{ color: var(--on-surface-variant) !important; }}

        /* Typography. */
        h1, h2, h3, h4, h5, h6 {{
            font-family: Inter, sans-serif !important;
            color: var(--on-surface) !important;
        }}
        h2 {{ font-size: 20px !important; }}
        h3, [data-testid="stMarkdownContainer"] h3 {{ font-size: 17px !important; }}
        p, label, span, div, .stMarkdown, .stText, .stCaption {{ color: var(--on-surface-variant); }}

        /* Technical inputs. */
        [data-baseweb="select"] > div,
        .stTextInput input, .stNumberInput input, .stDateInput input,
        textarea {{
            background: var(--surface-low) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            color: var(--on-surface) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 11px !important;
        }}
        [data-baseweb="select"] > div:hover,
        .stTextInput input:hover, .stDateInput input:hover,
        .stNumberInput input:hover, textarea:hover {{ border-color: var(--primary) !important; }}
        [data-baseweb="popover"] [data-baseweb="menu"], [role="listbox"] {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
        }}
        [role="option"] {{ font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important; }}
        [role="option"]:hover {{ background: var(--surface-high) !important; }}
        [data-baseweb="tag"] {{
            background: rgba(33,150,243,.16) !important;
            border: 1px solid rgba(158,202,255,.4) !important;
            border-radius: 2px !important;
        }}

        /* Dense technical tables. */
        [data-testid="stDataFrame"] {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            overflow: hidden !important;
        }}
        [data-testid="stDataFrame"] div {{
            color: var(--on-surface) !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 10.5px !important;
        }}

        /* Stitch-like chart frames. */
        [data-testid="stPlotlyChart"] {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
            padding: 5px !important;
            box-shadow: none !important;
        }}

        /* Status alerts use semantic saturation only. */
        .stAlert {{
            border-radius: var(--tech-radius) !important;
            border-width: 1px !important;
            font-family: 'JetBrains Mono', monospace !important;
            font-size: 11px !important;
        }}
        [data-testid="stExpander"] {{
            background: var(--surface-container) !important;
            border: 1px solid var(--outline-variant) !important;
            border-radius: var(--tech-radius) !important;
        }}

        @media (max-width: 1000px) {{
            :root {{ --left-nav-width: 205px; }}
            .custom-nav-item {{ padding-left: 10px !important; padding-right: 8px !important; }}
            .custom-nav-label {{ font-size: 10.5px !important; }}
            .tower-title {{ font-size: 19px !important; }}
        }}


        /* Jednolinijski padajući filteri */
        div[data-testid="stHorizontalBlock"]:has(button p) {{ align-items:center; }}
        [data-testid="stPopover"] > button {{
            height:42px !important; min-height:42px !important; width:100% !important;
            justify-content:flex-start !important; padding:0 13px !important;
            border-radius:3px !important; background:#181c22 !important;
            border:1px solid #404752 !important; box-shadow:none !important;
            font:600 10px/42px 'JetBrains Mono',monospace !important;
            color:#dbe6f5 !important; white-space:nowrap !important; overflow:hidden !important;
        }}
        [data-testid="stPopover"] > button:hover {{ border-color:#78a9ff !important; background:#1e242c !important; }}
        [data-testid="stPopoverBody"] {{ min-width:360px !important; max-width:min(520px,92vw) !important; }}

        /* Sažetak aktivnih filtera - mora biti globalan. */
        div[data-testid="stHorizontalBlock"]:has(.active-filter-strip) {{ gap:10px !important; margin-bottom:4px !important; }}
        .active-filter-strip {{
            min-height:27px !important;
            display:flex !important;
            align-items:center !important;
            gap:22px !important;
            padding:0 3px !important;
            color:#7f8b9d !important;
            font:500 9px/27px 'JetBrains Mono',monospace !important;
            text-transform:uppercase !important;
            letter-spacing:.35px !important;
            white-space:nowrap !important;
            overflow:hidden !important;
        }}
        .active-filter-strip span {{ color:#7f8b9d !important; margin-right:22px !important; }}
        .active-filter-strip b {{ color:#b8c7db !important; font-weight:700 !important; }}

        /* POPRAVKA FILTERA: tamni padajući meniji i čitljiv tekst bez kvarenja kalendara. */
        [data-testid="stPopoverBody"],
        [data-baseweb="popover"],
        [data-baseweb="popover"] > div,
        [data-baseweb="menu"],
        [role="listbox"] {{
            background-color:#111821 !important;
            color:#e9f2ff !important;
            border-color:#404752 !important;
        }}
        [data-testid="stPopoverBody"] *,
        [data-baseweb="popover"] *,
        [data-baseweb="menu"] *,
        [role="listbox"] * {{
            color:#e9f2ff !important;
        }}
        [role="option"],
        [data-baseweb="menu"] li,
        [data-baseweb="select"] span,
        [data-baseweb="select"] div {{
            color:#e9f2ff !important;
            background-color:transparent !important;
        }}
        [role="option"]:hover,
        [data-baseweb="menu"] li:hover {{
            background-color:#26313d !important;
            color:#ffffff !important;
        }}
        [aria-selected="true"][role="option"],
        [data-baseweb="menu"] li[aria-selected="true"] {{
            background-color:#0f365f !important;
            color:#ffffff !important;
        }}
        [data-baseweb="checkbox"] span,
        [data-testid="stCheckbox"] label p,
        [data-testid="stCheckbox"] label span {{
            color:#e9f2ff !important;
        }}
        [data-baseweb="select"] > div,
        [data-testid="stPopover"] > button,
        .stButton > button {{
            background:#181c22 !important;
            color:#e9f2ff !important;
            border:1px solid #404752 !important;
        }}
        [data-testid="stPopover"] > button p,
        .stButton > button p {{
            color:#e9f2ff !important;
        }}
        [data-baseweb="input"] input,
        .stDateInput input {{
            background:#0f1419 !important;
            color:#e9f2ff !important;
            border-color:#404752 !important;
        }}

        /* Kalendar: tamna tabela, bez belih krugova preko dana. */
        [data-baseweb="calendar"] {{
            background:#111821 !important;
            color:#e9f2ff !important;
            border:1px solid #404752 !important;
        }}
        [data-baseweb="calendar"] button {{
            background:transparent !important;
            color:#e9f2ff !important;
            border-radius:4px !important;
            box-shadow:none !important;
        }}
        [data-baseweb="calendar"] button:hover {{
            background:#26313d !important;
            color:#ffffff !important;
        }}
        [data-baseweb="calendar"] button[aria-selected="true"],
        [data-baseweb="calendar"] button[aria-pressed="true"] {{
            background:#9ecaff !important;
            color:#06121f !important;
            font-weight:800 !important;
        }}
        [data-baseweb="calendar"] button[aria-current="date"] {{
            border:1px solid #9ecaff !important;
        }}
        [data-baseweb="calendar"] [role="gridcell"] {{
            background:transparent !important;
        }}

        /* GLOBALNI KANBAN ZA AKCIJE - mora biti globalno, ne samo u tabu Kvarovi. */
        .module-command-bar {{ height:48px; display:grid; grid-template-columns:auto minmax(220px,1fr) auto; align-items:center; gap:12px; margin-bottom:12px; padding:0 10px; background:#181c22; border:1px solid #404752; border-radius:4px; }}
        .command-tabs{{display:flex;gap:5px}}
        .command-tab{{padding:6px 10px;color:#89919d;border:1px solid transparent;font:600 10px/13px 'JetBrains Mono',monospace}}
        .command-tab.active{{color:#9ecaff;background:#262a30;border-color:#404752}}
        .command-search{{max-width:310px;height:30px;display:flex;align-items:center;padding:0 10px;color:#89919d;background:#1c2026;border:1px solid #404752;border-radius:3px;font:500 10px 'JetBrains Mono',monospace}}
        .command-primary{{justify-self:end;padding:8px 15px;background:#9ecaff;color:#003258;border-radius:3px;font:700 10px 'JetBrains Mono',monospace}}
        .actions-kanban{{display:flex;gap:8px;min-height:470px;overflow-x:auto;padding-bottom:6px}}
        .action-column{{min-width:245px;max-width:310px;flex:1 0 245px;background:#0a0e14;border:1px solid #404752;border-radius:4px;overflow:hidden}}
        .action-column-header{{height:44px;display:flex;justify-content:space-between;align-items:center;padding:0 11px;border-top:3px solid var(--column-accent);border-bottom:1px solid #404752;color:#dfe2ea;font:600 10px 'JetBrains Mono',monospace;letter-spacing:.55px}}
        .action-column-header b{{padding:3px 5px;background:#1c2026;color:#9ecaff;font-size:9px}}
        .action-column-body{{padding:9px}}
        .action-card{{margin-bottom:9px;padding:11px;background:#1c2026;border:1px solid #404752;border-radius:3px}}
        .action-card-top,.action-card-footer{{display:flex;justify-content:space-between;align-items:center;gap:7px}}
        .priority-chip{{padding:3px 6px;border-radius:2px;font:700 8px 'JetBrains Mono',monospace}}
        .priority-high{{background:#93000a;color:#ffdad6}}
        .priority-medium{{background:#db7900;color:#2e1500}}
        .priority-low{{background:#153822;color:#c8f7d6}}
        .action-id{{color:#9ecaff;font:600 9px 'JetBrains Mono',monospace}}
        .action-title{{margin:10px 0 6px;color:#dfe2ea;font:600 12px/17px Inter,sans-serif}}
        .action-comment{{min-height:30px;color:#9ca7b5;font:400 10px/14px Inter,sans-serif}}
        .action-card-footer{{margin-top:10px;padding-top:8px;border-top:1px solid #31353b;color:#bfc7d4;font:500 9px 'JetBrains Mono',monospace}}
        .kanban-empty{{padding:22px 8px;color:#657080;text-align:center;font:500 9px 'JetBrains Mono',monospace}}
        .system-status-footer{{height:30px;display:flex;justify-content:space-between;align-items:center;margin-top:8px;padding:0 10px;background:#0a0e14;border:1px solid #404752;color:#89919d;font:500 8px 'JetBrains Mono',monospace}}
        .system-status-footer i{{display:inline-block;width:6px;height:6px;border-radius:50%;background:#42d392;box-shadow:0 0 5px rgba(66,211,146,.55)}}
        .actions-note{{margin-top:8px;color:#89919d;font:400 10px/15px Inter,sans-serif}}
        @media(max-width:1050px){{.actions-kanban{{grid-template-columns:repeat(4,260px)}}.creator-box{{display:none!important}}}}

        /* ============ TAMNA TEMA ZA PADAJUĆE MENIJE I KALENDAR ============ */
        /* Kontejner popovera (otvara se u portalu na nivou body-ja) */
        div[data-baseweb="popover"] div[data-baseweb="menu"],
        ul[data-baseweb="menu"],
        div[data-baseweb="calendar"],
        div[data-baseweb="calendar"] > div {{
            background-color: var(--panel-solid) !important;
            color: var(--text-hi) !important;
            border: 1px solid var(--border-strong) !important;
        }}
        /* --- Selectbox lista (npr. izbor alata) --- */
        ul[data-baseweb="menu"] li,
        li[role="option"] {{
            background-color: var(--panel-solid) !important;
            color: var(--text-md) !important;
        }}
        ul[data-baseweb="menu"] li:hover,
        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {{
            background-color: var(--accent-soft) !important;
            color: var(--text-hi) !important;
        }}
        /* --- Kalendar (date_input) --- */
        /* Sve unutra kreni od tamne pozadine da nema belih polja */
        div[data-baseweb="calendar"] * {{
            background-color: transparent !important;
            color: var(--text-md) !important;
        }}
        /* Zaglavlje sa mesecom/godinom i strelice */
        div[data-baseweb="calendar"] button {{
            color: var(--text-hi) !important;
        }}
        /* Nazivi dana u nedelji */
        div[data-baseweb="calendar"] [role="grid"] > div:first-child,
        div[data-baseweb="calendar"] abbr {{
            color: var(--text-lo) !important;
        }}
        /* Dani - hover */
        div[data-baseweb="calendar"] [role="gridcell"] > div:hover {{
            background-color: var(--accent-soft) !important;
            color: var(--text-hi) !important;
        }}
        /* Izabrani dan */
        div[data-baseweb="calendar"] [aria-selected="true"] > div,
        div[data-baseweb="calendar"] [aria-selected="true"] {{
            background-color: var(--accent) !important;
            color: #05202b !important;
        }}
        /* Danas */
        div[data-baseweb="calendar"] [aria-label*="Today"] > div {{
            border: 1px solid var(--accent-line) !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

set_background(APP_DIR / "background_tooling.png")


def image_to_data_uri(image_path: str) -> str:
    try:
        path = Path(__file__).with_name(image_path)
        suffix = path.suffix.lower().replace(".", "") or "png"
        if suffix == "jpg":
            suffix = "jpeg"
        encoded = base64.b64encode(path.read_bytes()).decode()
        return f"data:image/{suffix};base64,{encoded}"
    except Exception:
        return ""


logo_uri = image_to_data_uri(APP_DIR / "company_logo.png")
if logo_uri:
    logo_html = f'<img src="{logo_uri}" alt="Lianbo Precision Technology logo">'
else:
    logo_html = '<div class="logo-missing">Logo kompanije nije dodat.<br>Ubaci pravi fajl kao <b>company_logo.png</b></div>'
st.markdown('<meta http-equiv="refresh" content="900">', unsafe_allow_html=True)


# =========================================================
# POMOĆNE FUNKCIJE
# =========================================================
def norm_col(col) -> str:
    text = str(col).strip().upper()
    text = text.replace("Š", "S").replace("Đ", "DJ").replace("Č", "C").replace("Ć", "C").replace("Ž", "Z")
    text = text.replace("_", " ").replace("/", " ").replace("-", " ")
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_tool_name(value) -> str:
    """Sređuje naziv alata za poređenje i prikaz.
    Najvažnije: više razmaka se tretira kao jedan razmak, pa npr.
    'LK4-M1197  #1 LK4' i 'LK4-M1197 #1 LK4' postaju isti alat.
    """
    if pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if text.lower() in ["nan", "none", "nat", ""]:
        return ""
    return text




def compact_tool_key(value) -> str:
    """Ključ za poređenje alata koji ignoriše razmake, crtice i znakove.
    Ovo rešava slučajeve gde je u istoriji preventive alat upisan malo drugačije
    nego u Total punch tabu, npr. dodat razmak, crtica ili # oznaka.
    """
    text = strip_accents(normalize_tool_name(value)).upper()
    text = re.sub(r"[^A-Z0-9#]+", "", text)
    return text


def tool_code_key(value) -> str:
    """Rezervni ključ po šifri alata, npr. M1108.
    Koristi se samo kao fallback ako se puni naziv ne poklopi.
    """
    text = strip_accents(normalize_tool_name(value)).upper()
    project_match = re.search(r"(APP\s*350|APP\s*550|LK\s*-?\s*4|LK\s*-?\s*3|EMR\s*4|VITESKO)", text)
    mold_match = re.search(r"\bM\s*-?\s*(\d{3,5})\b", text)
    cavity_match = re.search(r"#\s*(\d+)", text)
    parts = []
    if project_match:
        parts.append(re.sub(r"\s+|-", "", project_match.group(1)))
    if mold_match:
        parts.append("M" + mold_match.group(1))
    if cavity_match:
        parts.append("#" + cavity_match.group(1))
    if not parts and mold_match:
        parts.append("M" + mold_match.group(1))
    return "|".join(parts)


def tool_mold_key(value) -> str:
    """Najširi fallback samo po šifri kalupa, npr. M1108."""
    text = strip_accents(normalize_tool_name(value)).upper()
    mold_match = re.search(r"\bM\s*-?\s*(\d{3,5})\b", text)
    return "M" + mold_match.group(1) if mold_match else ""

def strip_accents(value: str) -> str:
    tekst = str(value or "").strip().lower()
    tekst = unicodedata.normalize("NFKD", tekst)
    return "".join(ch for ch in tekst if not unicodedata.combining(ch))


def normalizuj_status_kvara(value) -> str:
    """Pretvara različite upise iz Google Sheets-a u status koji Kanban koristi.
    Prazan status tretiramo kao Završeno zbog starih podataka.
    """
    raw = str(value or "").strip()
    norm = strip_accents(raw)
    if norm in ["", "nan", "none", "nat"]:
        return "Završeno"

    if any(x in norm for x in ["prijav", "novo", "novi", "open", "pending", "otvor"]):
        return "Prijavljeno"
    if any(x in norm for x in ["u radu", "uradu", "rad", "working", "progress", "proces"]):
        return "U radu"
    if any(x in norm for x in ["ceka deo", "ceka djel", "ceka del", "cekadeo", "delovi", "deo", "parts"]):
        return "Čeka deo"
    if any(x in norm for x in ["ceka kinu", "kina", "kinez", "china", "chinese"]):
        return "Čeka Kinu"
    if any(x in norm for x in ["ponov", "repeat", "reopen"]):
        return "Ponovljen kvar"
    if any(x in norm for x in ["zavrs", "resen", "rijesen", "gotov", "closed", "done", "finish"]):
        return "Završeno"

    return raw.title() if raw else "Završeno"

def find_col(df: pd.DataFrame, candidates):
    normalized = {norm_col(c): c for c in df.columns}
    for cand in candidates:
        if norm_col(cand) in normalized:
            return normalized[norm_col(cand)]
    for col in df.columns:
        ncol = norm_col(col)
        for cand in candidates:
            if norm_col(cand) in ncol:
                return col
    return None


def to_number(value, default=0):
    if pd.isna(value):
        return default
    if isinstance(value, (int, float)):
        return value
    txt = str(value).strip().replace(",", ".")
    txt = re.sub(r"[^0-9\.\-]", "", txt)
    if txt in ["", ".", "-", "-."]:
        return default
    try:
        return float(txt)
    except Exception:
        return default


def trajanje_u_minute(value):
    if pd.isna(value):
        return 0.0
    txt = str(value).strip()
    if txt == "" or txt.lower() in ["nan", "none", "nat"]:
        return 0.0
    if ":" in txt:
        parts = txt.split(":")
        try:
            if len(parts) == 3:
                return float(parts[0]) * 60 + float(parts[1]) + float(parts[2]) / 60
            if len(parts) == 2:
                return float(parts[0]) * 60 + float(parts[1])
        except Exception:
            pass
    txt = txt.lower().replace("minuta", "").replace("min", "").replace(",", ".").strip()
    return to_number(txt, 0.0)


def kpi_card(title, value, note=""):
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-title">{title}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )




def show_dark_dataframe(df, width="stretch", height="content"):
    """Prikaz tabele sa tamnim stilom, da ne iskače bela tabela u dashboardu.
    Streamlit novije verzije ne prihvataju height=None, zato je podrazumevano height='content'.
    """
    if df is None:
        st.info("Nema podataka za prikaz.")
        return

    # Za svaki slučaj: ako neka stara funkcija prosledi None, pretvori u dozvoljenu vrednost.
    if height is None:
        height = "content"

    try:
        styled = (
            df.style
            .set_properties(**{
                "background-color": "#131d2e",
                "color": "#f4f8fd",
                "border-color": "#2a3a54",
                "font-family": "Inter, sans-serif",
                "font-size": "13px",
            })
            .set_table_styles([
                {"selector": "th", "props": [("background-color", "#182640"), ("color", "#f4f8fd"), ("font-weight", "700"), ("border-color", "#33445f"), ("text-transform", "uppercase"), ("font-size", "11.5px"), ("letter-spacing", ".4px")]},
                {"selector": "td", "props": [("background-color", "#131d2e"), ("color", "#dbe6f5"), ("border-color", "#2a3a54")]},
                {"selector": "tbody tr:nth-child(even) td", "props": [("background-color", "#101929")]},
                {"selector": "tbody tr:hover td", "props": [("background-color", "#1a2c42")]},
            ])
        )
        st.dataframe(styled, use_container_width=use_container_width, height=height)
    except Exception:
        st.dataframe(df, use_container_width=use_container_width, height=height)

PLOTLY_COLORWAY = ["#9ecaff", "#2196f3", "#ffb77b", "#ffb4ab", "#78dba9", "#c8c6c5", "#89919d"]

# Jedinstvene semafor boje za sve grafikone:
# OK = zeleno, praćenje/srednje = narandžasto, loše/kritično = crveno.
STATUS_COLOR_MAP = {
    "🔴 Kritično": "#ff2d35",
    "🟡 Praćenje": "#f5b942",
    "🟢 OK": "#42d392",
    "🔴 Za preventivu": "#ff2d35",
    "🟡 Blizu preventive": "#f5b942",
    "⚪ Postavi početno stanje": "#9ca7b5",
    "⚫ Prešao životni vek": "#7b8794",
    "🔴 Nema": "#ff2d35",
    "🟡 Ispod minimuma": "#f5b942",
    "🟢 Dobro": "#42d392",
    "🔵 Preko maksimuma": "#4fa8f5",
}


def plotly_layout(fig, height=None):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#1c2026",
        font=dict(color="#dfe2ea", size=12, family="JetBrains Mono, monospace"),
        title_font=dict(color="#dfe2ea", size=14, family="Inter, sans-serif"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#bfc7d4", family="JetBrains Mono, monospace", size=10)),
        colorway=PLOTLY_COLORWAY,
        margin=dict(t=56, l=10, r=10, b=10),
        xaxis=dict(gridcolor="#31353b", zerolinecolor="#404752", color="#bfc7d4"),
        yaxis=dict(gridcolor="#31353b", zerolinecolor="#404752", color="#bfc7d4"),
    )
    fig.update_layout(
        hoverlabel=dict(bgcolor="#262a30", bordercolor="#404752", font=dict(color="#dfe2ea", size=11, family="JetBrains Mono, monospace")),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#89919d", activecolor="#9ecaff"),
        bargap=0.28,
    )
    fig.update_traces(marker_line_width=0)
    if height:
        fig.update_layout(height=height)
    return fig


def klasifikuj_kvar(opis):
    # Tekst se najpre očisti od dijakritika (š→s, č/ć→c, ž→z) i đ→dj, pa se poredi
    # sa ključnim rečima bez kvačica. Tako "nož", "noz", "kaiš", "kais" itd. rade isto.
    tekst = strip_accents(str(opis)).replace("đ", "dj")
    # "remen"/"remena"/"remenica" = kaiš, ali paziti da se ne pobrka sa "vremenski".
    # Zato tražimo "remen" samo na početku reči (granica reči), a ne kao deo druge reči.
    if re.search(r"\bremen", tekst):
        return "Zupčasti kaiš / rotacija"
    # Sve što ima veze sa elektroventilom ide u pneumatiku, bez obzira na ostatak
    # opisa. Hvata: elektroventil, elektro ventil, elektro-ventil, el. ventil,
    # elektromagnetni ventil (i množinu: elektroventili, elektroventila...).
    if re.search(r"\bel(?:ektro\w*|\.)?[\s-]*ventil", tekst):
        return "Pneumatika / cilindri"
    # Redosled je bitan: prvi pogodak pobeđuje, pa specifičnije kategorije idu prve.
    groups = {
        "Magnetizacija": ["demagnet", "namagnet", "razmagnet", "magnetiz", "magnetis"],
        "Zupčasti kaiš / rotacija": ["zupcast", "kais", "rotacij", "lezaj", "pogonski kais"],
        "Zakivanje": ["zakiv", "prokiv", "rivet", "prstenovanje"],
        "Missfeed / feeder": ["misfeed", "missfeed", "mis feed", "feeder", "fider", "uvlac", "ne uvlac", "vodjenje trake", "vodjenje lima", "posmak", "feed"],
        "Lamele (rasipanje/slaganje)": ["rasipanje", "lamel", "ispustanje", "razdvaja", "slaganje pak", "prihvat lamel", "otpada lamel", "poslednja lamel", "donja lamel"],
        "Stator / rotor": ["stator", "slot", "krivljenje", "zaglavljivanje", "prihvat rotora", "ravnost", "paralelnost paketa"],
        "Pinovi / pozicioniranje": ["pin", "pinov", "pozicion", "centrir", "vodjic", "zapinjanje lim", "rupa pozicion"],
        "Noževi / dimenzije": ["noz", "nozev", "ostr", "brus", "obrada gornj", "obrada donj", "dimenzij", "geometrij", "zazor", "zarez", "v-zarez", "habanj", "istrosen"],
        "Opiljci / otpad": ["opiljak", "opiljci", "opiljc", "spena", "otpad", "zapus", "odvod", "prsten", "povlacenje", "grat"],
        "Senzori": ["senzor", "sensor", "fotocelij", "fotoceli", "ne vidi", "signal", "prekidac"],
        "Hidraulika": ["hidraul", "ulje", "klip", "pritisak ulja"],
        "Vijci / spojevi": ["vijak", "vijc", "vijk", "navoj", "moment zateza", "zavrtanj"],
        "Pneumatika / cilindri": ["pneum", "cilind", "vazduh", "elektroventil", "ventil", "crev", "spojnic", "regulator", "curenje", "pritisak vazduha"],
        "Podešavanje / operater": ["podes", "operater", "nije znao", "nije znala", "neobuc", "improviz", "pogresno postav"],
    }
    for category, words in groups.items():
        if any(w in tekst for w in words):
            return category
    return "Ostalo"


# =========================================================
# UČITAVANJE PODATAKA
# =========================================================
@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def download_bytes(url: str) -> bytes:
    last_error = None
    for _ in range(3):
        try:
            response = requests.get(url, timeout=90)
            if response.status_code == 200 and len(response.content) > 50:
                return response.content
            last_error = f"HTTP {response.status_code}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"Ne mogu da preuzmem podatke: {last_error}")


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_udarce():
    content = download_bytes(EXCEL_URL_UDARCI)
    excel = pd.ExcelFile(BytesIO(content))
    sheet_names = excel.sheet_names
    start_idx = sheet_names.index(START_SHEET_UDARCI) if START_SHEET_UDARCI in sheet_names else 0

    month_sheets = [s for s in sheet_names[start_idx:] if re.match(r"^\d{2}\.\d{4}", str(s).strip())]
    rows = []
    for sheet in month_sheets:
        try:
            df = pd.read_excel(excel, sheet_name=sheet, header=1)
        except Exception:
            continue
        if df.empty:
            continue
        alat_col = df.columns[0]
        day_cols = []
        for col in df.columns[1:]:
            if pd.notna(pd.to_datetime(col, errors="coerce")):
                day_cols.append(col)
                continue
            try:
                d = int(str(col).strip())
                if 1 <= d <= 31:
                    day_cols.append(col)
            except Exception:
                pass
        if not day_cols:
            continue
        temp = pd.DataFrame()
        temp["ALAT"] = df[alat_col].apply(normalize_tool_name)
        temp["MESEC"] = sheet
        temp["UDARCI"] = df[day_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        temp = temp.dropna(subset=["ALAT"])
        temp = temp[temp["ALAT"].astype(str).str.strip() != ""]
        rows.append(temp)

    if not rows:
        return pd.DataFrame(columns=["ALAT", "MESEC", "UDARCI"]), month_sheets
    result = pd.concat(rows, ignore_index=True)
    result["UDARCI"] = pd.to_numeric(result["UDARCI"], errors="coerce").fillna(0)
    return result, month_sheets


def odredi_projekat_iz_alata(alat: str) -> str:
    """Određuje projekat iz naziva alata za zbirni prikaz udaraca."""
    naziv = normalize_tool_name(alat).upper()
    naziv_norm = re.sub(r"[^A-Z0-9]+", " ", naziv)
    if "APP350" in naziv_norm or re.search(r"(?:^|\s)350(?:\s|$)", naziv_norm):
        return "APP350"
    if "APP550" in naziv_norm or re.search(r"(?:^|\s)550(?:\s|$)", naziv_norm):
        return "APP550"
    if any(token in naziv_norm for token in ["LK4", "LK 4"]):
        return "LK-4"
    if any(token in naziv_norm for token in ["EMR4", "VITESKO", "VITESCO"]):
        return "VITESKO EMR4"
    return "Ostalo"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_udarce_dnevno() -> pd.DataFrame:
    """Učitava udarce na nivou pojedinačnog datuma za lokalni periodni pregled."""
    content = download_bytes(EXCEL_URL_UDARCI)
    excel = pd.ExcelFile(BytesIO(content))
    sheet_names = excel.sheet_names
    start_idx = sheet_names.index(START_SHEET_UDARCI) if START_SHEET_UDARCI in sheet_names else 0
    month_sheets = [s for s in sheet_names[start_idx:] if re.match(r"^\d{2}\.\d{4}$", str(s).strip())]

    rows = []
    for sheet in month_sheets:
        try:
            df = pd.read_excel(excel, sheet_name=sheet, header=1)
        except Exception:
            continue
        if df.empty:
            continue

        alat_col = df.columns[0]
        try:
            mesec_broj, godina = [int(x) for x in str(sheet).split(".")]
        except Exception:
            continue

        for col in df.columns[1:]:
            datum = pd.NaT
            parsed = pd.to_datetime(col, errors="coerce")
            if pd.notna(parsed):
                datum = pd.Timestamp(parsed).normalize()
            else:
                try:
                    dan = int(float(str(col).strip()))
                    datum = pd.Timestamp(year=godina, month=mesec_broj, day=dan)
                except Exception:
                    continue

            values = pd.to_numeric(df[col], errors="coerce").fillna(0)
            for alat_raw, broj in zip(df[alat_col], values):
                alat = normalize_tool_name(alat_raw)
                if not alat:
                    continue
                rows.append({
                    "DATUM": datum,
                    "ALAT": alat,
                    "MESEC": sheet,
                    "PROJEKAT": odredi_projekat_iz_alata(alat),
                    "UDARCI": float(broj or 0),
                })

    if not rows:
        return pd.DataFrame(columns=["DATUM", "ALAT", "MESEC", "PROJEKAT", "UDARCI"])

    out = pd.DataFrame(rows)
    out["DATUM"] = pd.to_datetime(out["DATUM"], errors="coerce")
    out["UDARCI"] = pd.to_numeric(out["UDARCI"], errors="coerce").fillna(0)
    out = out.dropna(subset=["DATUM"])
    return out.reset_index(drop=True)



def lifetime_na_datum(
    alat: str,
    datum,
    trenutni_lifetime: float,
    udarci_dnevno_df: pd.DataFrame,
) -> tuple[float, float, bool, str]:
    """Računa lifetime stanje alata na kraju izabranog datuma.

    Total punch predstavlja trenutno stanje. Za retroaktivni datum oduzimaju se
    svi udarci zabeleženi POSLE tog datuma. Udarci na sam izabrani datum ostaju
    uključeni, jer se preventiva tretira kao stanje na kraju tog dana.

    Vraća: (lifetime_tada, udarci_posle_datuma, pouzdano, napomena)
    """
    alat_norm = normalize_tool_name(alat)
    datum_ts = pd.to_datetime(datum, errors="coerce")
    current = max(float(to_number(trenutni_lifetime, 0)), 0.0)

    if not alat_norm or pd.isna(datum_ts):
        return current, 0.0, False, "Nije moguće odrediti alat ili datum."
    datum_ts = pd.Timestamp(datum_ts).normalize()

    if udarci_dnevno_df is None or udarci_dnevno_df.empty:
        return current, 0.0, False, "Dnevni podaci o udarcima nisu dostupni; proveri stanje ručno."

    dnevno = udarci_dnevno_df.copy()
    if not {"DATUM", "ALAT", "UDARCI"}.issubset(dnevno.columns):
        return current, 0.0, False, "Dnevni podaci nemaju potrebne kolone; proveri stanje ručno."

    dnevno["DATUM"] = pd.to_datetime(dnevno["DATUM"], errors="coerce").dt.normalize()
    dnevno["ALAT_NORM"] = dnevno["ALAT"].apply(normalize_tool_name)
    dnevno["ALAT_KEY"] = dnevno["ALAT"].apply(compact_tool_key)
    dnevno["ALAT_CODE_KEY"] = dnevno["ALAT"].apply(tool_code_key)
    dnevno["ALAT_MOLD_KEY"] = dnevno["ALAT"].apply(tool_mold_key)
    dnevno["UDARCI"] = pd.to_numeric(dnevno["UDARCI"], errors="coerce").fillna(0)
    alat_key = compact_tool_key(alat_norm)
    code_key = tool_code_key(alat_norm)
    mold_key = tool_mold_key(alat_norm)
    alat_df = dnevno[dnevno["ALAT_KEY"] == alat_key].dropna(subset=["DATUM"])
    if alat_df.empty and code_key:
        alat_df = dnevno[dnevno["ALAT_CODE_KEY"] == code_key].dropna(subset=["DATUM"])
    if alat_df.empty and mold_key:
        alat_df = dnevno[dnevno["ALAT_MOLD_KEY"] == mold_key].dropna(subset=["DATUM"])

    if alat_df.empty:
        return current, 0.0, False, "Za izabrani alat nema dnevnih podataka; proveri stanje ručno."

    prvi_datum = alat_df["DATUM"].min()
    poslednji_datum = alat_df["DATUM"].max()
    udarci_posle = float(alat_df.loc[alat_df["DATUM"] > datum_ts, "UDARCI"].sum())
    lifetime_tada = max(current - udarci_posle, 0.0)

    pouzdano = datum_ts >= prvi_datum
    if datum_ts < prvi_datum:
        napomena = (
            f"Izabrani datum je pre prvog dostupnog dnevnog podatka ({prvi_datum:%d.%m.%Y}). "
            "Automatski obračun možda nije potpun."
        )
    elif datum_ts > poslednji_datum:
        napomena = (
            f"Izabrani datum je posle poslednjeg dostupnog podatka ({poslednji_datum:%d.%m.%Y}); "
            "koristi se trenutno lifetime stanje."
        )
    else:
        napomena = (
            f"Automatski obračun: trenutno stanje {current:,.0f} − "
            f"{udarci_posle:,.0f} udaraca posle {datum_ts:%d.%m.%Y} = {lifetime_tada:,.0f}."
        )
    return lifetime_tada, udarci_posle, pouzdano, napomena


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_total_punch_lifetime() -> pd.DataFrame:
    """Učitava procenjeni lifetime broj udaraca iz taba Total punch.
    Pošto struktura može biti različita, program traži redove sa nazivom alata i uzima najveću numeričku vrednost u redu kao ukupni lifetime.
    """
    try:
        content = download_bytes(EXCEL_URL_UDARCI)
        excel = pd.ExcelFile(BytesIO(content))
        sheet_name = None
        for sh in excel.sheet_names:
            if norm_col(sh) == norm_col("Total punch"):
                sheet_name = sh
                break
        if sheet_name is None:
            for sh in excel.sheet_names:
                if "TOTAL" in norm_col(sh) and "PUNCH" in norm_col(sh):
                    sheet_name = sh
                    break
        if sheet_name is None:
            return pd.DataFrame(columns=["ALAT", "LIFETIME_UDARCI", "IZVOR"])
        raw = pd.read_excel(excel, sheet_name=sheet_name, header=None, dtype=object)
        raw = raw.dropna(how="all").dropna(axis=1, how="all")
        if raw.empty:
            return pd.DataFrame(columns=["ALAT", "LIFETIME_UDARCI", "IZVOR"])
        rows = []
        for _, row in raw.iterrows():
            vals = list(row.values)
            alat = ""
            for v in vals[:3]:
                txt = str(v).strip()
                if txt and txt.lower() not in ["nan", "none"]:
                    n = norm_col(txt)
                    if any(x in n for x in ["SUMMARY", "TABLE", "TOTAL PUNCH", "DIE PUNCHING", "PRODUCT NAME", "PRODUCTION", "ALAT", "TOOL", "MOLD", "MOULD", "KALUP", "UKUPNO", "TOTAL", "合计", "产品名称", "模具编号"]):
                        continue
                    # Naziv alata obično sadrži projekat/broj, npr. APP350, APP550, LK4, EMR4...
                    # Tako nećemo pokupiti pomoćne naslove ili prazne redove.
                    if not any(token in n for token in ["APP", "LK", "EMR", "AIDA", "M102", "M108", "M119"]):
                        continue
                    alat = normalize_tool_name(txt)
                    break
            if not alat:
                continue
            numeric_vals = []
            for v in vals[1:]:
                if isinstance(v, str) and v.strip().startswith("="):
                    continue
                num = to_number(v, default=None)
                if num is not None and pd.notna(num) and num > 0:
                    numeric_vals.append(float(num))
            # VAŽNO: alat sa 0 udaraca mora da ostane u preventivi.
            # Ako je total ćelija prazna ili ima #ERROR!, tretiramo lifetime kao 0, a ne izbacujemo red.
            lifetime = max(numeric_vals) if numeric_vals else 0.0
            rows.append({"ALAT": alat, "LIFETIME_UDARCI": lifetime, "IZVOR": sheet_name})
        out = pd.DataFrame(rows)
        if out.empty:
            return pd.DataFrame(columns=["ALAT", "LIFETIME_UDARCI", "IZVOR"])
        out["ALAT"] = out["ALAT"].apply(normalize_tool_name)
        out = out[out["ALAT"].astype(str).str.strip() != ""]
        out = out.groupby("ALAT", as_index=False).agg(LIFETIME_UDARCI=("LIFETIME_UDARCI", "max"), IZVOR=("IZVOR", "first"))
        out["LIFETIME_UDARCI"] = pd.to_numeric(out["LIFETIME_UDARCI"], errors="coerce").fillna(0)
        return out.sort_values("LIFETIME_UDARCI", ascending=False).reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["ALAT", "LIFETIME_UDARCI", "IZVOR"])


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_preventiva_istorija() -> pd.DataFrame:
    cols = ["ID", "DATUM", "ALAT", "TIP_ZAPISA", "LIFETIME_UDARCI", "UDARCI_OD_PRETHODNE_PREVENTIVE", "INTERVAL_PREVENTIVE", "ZONA_ZIVOTA", "OPIS", "RADIO", "NAPOMENA", "CREATED_AT"]
    try:
        content = download_bytes(EXCEL_URL_UDARCI)
        excel = pd.ExcelFile(BytesIO(content))
        sheet_name = None
        for sh in excel.sheet_names:
            if norm_col(sh) == norm_col(SHEET_PREVENTIVA_ISTORIJA):
                sheet_name = sh
                break
        if sheet_name is None:
            return pd.DataFrame(columns=cols)
        df = pd.read_excel(excel, sheet_name=sheet_name, dtype=object)
        if df.empty:
            return pd.DataFrame(columns=cols)
        df.columns = [str(c).strip().upper() for c in df.columns]
        rename = {}
        for target, candidates in {
            "DATUM": ["DATUM", "DATE"],
            "ALAT": ["ALAT", "TOOL", "KALUP"],
            "TIP_ZAPISA": ["TIP_ZAPISA", "TIP ZAPISA", "TIP", "VRSTA"],
            "LIFETIME_UDARCI": ["LIFETIME_UDARCI", "LIFETIME UDARCI", "UKUPNO UDARACA", "TOTAL PUNCH"],
            "UDARCI_OD_PRETHODNE_PREVENTIVE": ["UDARCI_OD_PRETHODNE_PREVENTIVE", "UDARCI OD PRETHODNE PREVENTIVE"],
            "INTERVAL_PREVENTIVE": ["INTERVAL_PREVENTIVE", "INTERVAL PREVENTIVE"],
            "ZONA_ZIVOTA": ["ZONA_ZIVOTA", "ZONA ZIVOTA", "ZONA ŽIVOTA"],
            "OPIS": ["OPIS", "STA JE URADJENO", "ŠTA JE URAĐENO", "URADJENO"],
            "RADIO": ["RADIO", "KO JE RADIO", "OSOBA"],
            "NAPOMENA": ["NAPOMENA", "NOTE"],
            "CREATED_AT": ["CREATED_AT", "CREATED AT", "UPISANO"],
        }.items():
            col = find_col(df, candidates)
            if col:
                rename[col] = target
        df = df.rename(columns=rename)
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df["DATUM"] = pd.to_datetime(df["DATUM"], errors="coerce", dayfirst=True)
        df["CREATED_AT"] = pd.to_datetime(df["CREATED_AT"], errors="coerce", dayfirst=True)
        for c in ["LIFETIME_UDARCI", "UDARCI_OD_PRETHODNE_PREVENTIVE", "INTERVAL_PREVENTIVE"]:
            df[c] = pd.to_numeric(df[c].apply(to_number), errors="coerce").fillna(0)
        for c in ["ALAT", "TIP_ZAPISA", "ZONA_ZIVOTA", "OPIS", "RADIO", "NAPOMENA"]:
            df[c] = df[c].astype(str).replace(["nan", "None", "<NA>"], "").str.strip()
        df["ALAT"] = df["ALAT"].apply(normalize_tool_name)
        return df[cols].reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=cols)


def dopuni_total_punch_sa_svim_alatima(total_df: pd.DataFrame, udarci_df: pd.DataFrame) -> pd.DataFrame:
    """Za preventivu moraju da postoje i alati koji imaju 0 udaraca.
    Total punch nekad izbaci prazno/#ERROR za nove alate, a mesečni tabovi ih ipak imaju.
    Ova funkcija pravi master listu: Total punch + svi alati iz mesečnih tabova.
    Ako neki alat nema lifetime vrednost, dobija 0.
    """
    base_cols = ["ALAT", "LIFETIME_UDARCI", "IZVOR"]
    frames = []
    if total_df is not None and not total_df.empty:
        t = total_df.copy()
        t["ALAT"] = t["ALAT"].apply(normalize_tool_name)
        t["LIFETIME_UDARCI"] = pd.to_numeric(t["LIFETIME_UDARCI"].apply(lambda x: to_number(x, 0)), errors="coerce").fillna(0)
        if "IZVOR" not in t.columns:
            t["IZVOR"] = "Total punch"
        frames.append(t[base_cols])
    if udarci_df is not None and not udarci_df.empty and "ALAT" in udarci_df.columns:
        u = pd.DataFrame({
            "ALAT": udarci_df["ALAT"].apply(normalize_tool_name),
            "LIFETIME_UDARCI": 0.0,
            "IZVOR": "Mesečni tabovi / alat bez lifetime udaraca"
        })
        frames.append(u[base_cols])
    if not frames:
        return pd.DataFrame(columns=base_cols)
    out = pd.concat(frames, ignore_index=True)
    out = out[out["ALAT"].astype(str).str.strip() != ""]
    out = out.groupby("ALAT", as_index=False).agg(
        LIFETIME_UDARCI=("LIFETIME_UDARCI", "max"),
        IZVOR=("IZVOR", lambda x: ", ".join(sorted(set([str(v) for v in x if str(v).strip()]))[:3]))
    )
    return out.sort_values(["LIFETIME_UDARCI", "ALAT"], ascending=[False, True]).reset_index(drop=True)



def preventive_interval_for_lifetime(lifetime: float) -> tuple[int, str, float]:
    life = max(float(lifetime or 0), 0.0)
    pct = life / TOOL_LIFE_PUNCHES if TOOL_LIFE_PUNCHES else 0
    if life < PREVENTIVE_LIMIT_20:
        return PREVENTIVE_INTERVAL_FIRST, "0–20%", pct
    if life < PREVENTIVE_LIMIT_80:
        return PREVENTIVE_INTERVAL_MIDDLE, "20–80%", pct
    if life <= TOOL_LIFE_PUNCHES:
        return PREVENTIVE_INTERVAL_LAST, "80–100%", pct
    return PREVENTIVE_INTERVAL_LAST, "PREKO 100%", pct


def build_preventiva_status(total_punch_df: pd.DataFrame, istorija_df: pd.DataFrame, udarci_dnevno_df: pd.DataFrame = None) -> pd.DataFrame:
    if total_punch_df is None or total_punch_df.empty:
        return pd.DataFrame(columns=["ALAT", "LIFETIME_UDARCI", "ZONA_ZIVOTA", "PROCENAT_ZIVOTA", "INTERVAL_PREVENTIVE", "POSLEDNJA_PREVENTIVA_DATUM", "POSLEDNJA_PREVENTIVA_UDARCI", "UDARCI_OD_PREVENTIVE", "OSTALO_DO_PREVENTIVE", "PREKORACENJE", "STATUS_PREVENTIVE", "OPIS_POSLEDNJE"])

    # Pripremi dnevne udarce po alatu da bismo mogli tačno da izračunamo koliko je
    # udaraca ostvareno POSLE datuma preventive. Ovo je ključno za retroaktivne unose:
    # ne oslanjamo se na to da je korisnik u istoriji ručno upisao tačan lifetime broj.
    dnevno_prep = None
    if udarci_dnevno_df is not None and not udarci_dnevno_df.empty and {"DATUM", "ALAT", "UDARCI"}.issubset(udarci_dnevno_df.columns):
        dnevno_prep = udarci_dnevno_df.copy()
        dnevno_prep["DATUM"] = pd.to_datetime(dnevno_prep["DATUM"], errors="coerce").dt.normalize()
        dnevno_prep["UDARCI"] = pd.to_numeric(dnevno_prep["UDARCI"], errors="coerce").fillna(0)
        dnevno_prep["ALAT_KEY"] = dnevno_prep["ALAT"].apply(compact_tool_key)
        dnevno_prep["ALAT_CODE_KEY"] = dnevno_prep["ALAT"].apply(tool_code_key)
        dnevno_prep["ALAT_MOLD_KEY"] = dnevno_prep["ALAT"].apply(tool_mold_key)
        dnevno_prep = dnevno_prep.dropna(subset=["DATUM"])

    def udarci_posle_datuma(alat_naziv: str, datum_prev) -> float:
        """Zbir dnevnih udaraca STROGO posle datuma preventive (za taj alat).
        Vraća None ako nema dnevnih podataka za taj alat ili je datum pre prvog
        dnevnog zapisa (tada sabiranje ne bi bilo potpuno, pa se koristi upisani broj)."""
        if dnevno_prep is None:
            return None
        d = pd.to_datetime(datum_prev, errors="coerce")
        if pd.isna(d):
            return None
        d = pd.Timestamp(d).normalize()
        a_key = compact_tool_key(alat_naziv)
        c_key = tool_code_key(alat_naziv)
        m_key = tool_mold_key(alat_naziv)
        sub = dnevno_prep[dnevno_prep["ALAT_KEY"] == a_key]
        if sub.empty and c_key:
            sub = dnevno_prep[dnevno_prep["ALAT_CODE_KEY"] == c_key]
        if sub.empty and m_key:
            sub = dnevno_prep[dnevno_prep["ALAT_MOLD_KEY"] == m_key]
        if sub.empty:
            return None
        prvi = sub["DATUM"].min()
        if pd.notna(prvi) and d < prvi:
            # Datum preventive je pre početka dnevnog praćenja -> ne možemo pouzdano
            # da saberemo sve udarce od tada; neka pozivalac koristi upisani broj.
            return None
        return float(sub.loc[sub["DATUM"] > d, "UDARCI"].sum())

    def _tip_zapisa_norm(v) -> str:
        """Svodi TIP_ZAPISA na 'PREVENTIVA' ili 'POCETNO_STANJE' (ili '' ako je nepoznato)."""
        n = strip_accents(str(v or "")).upper().replace(" ", "").replace("_", "").replace("-", "")
        if "POCETNO" in n or "POCETN" in n or "INITIAL" in n:
            return "POCETNO_STANJE"
        if "PREVENTIV" in n:
            return "PREVENTIVA"
        return ""

    def _izaberi_glavni(group):
        """Bira merodavan zapis za alat.
        PREVENTIVA (stvarno urađena preventiva) UVEK ima prednost nad POCETNO_STANJE.
        Ako za alat postoji bar jedna preventiva, početno stanje se zanemaruje,
        a uzima se najnovija preventiva po datumu. Ako preventive nema, uzima se
        poslednji zapis (po pravilu POCETNO_STANJE)."""
        g = group.sort_values(["DATUM_SORT", "CREATED_SORT"], na_position="first")
        prev = g[g["TIP_NORM"] == "PREVENTIVA"]
        if not prev.empty:
            return prev.iloc[-1]
        return g.iloc[-1]

    latest = {}
    latest_by_code = {}
    latest_by_mold = {}
    if istorija_df is not None and not istorija_df.empty:
        hist = istorija_df.copy()
        hist["ALAT"] = hist["ALAT"].apply(normalize_tool_name)
        hist = hist[hist["ALAT"].astype(str).str.strip() != ""]
        # Datum preventive je merodavan za redosled (bitno za retroaktivne unose).
        hist["DATUM_SORT"] = pd.to_datetime(hist["DATUM"], errors="coerce")
        hist["CREATED_SORT"] = pd.to_datetime(hist["CREATED_AT"], errors="coerce")
        hist["DATUM_SORT"] = hist["DATUM_SORT"].fillna(hist["CREATED_SORT"])
        hist["ALAT_KEY"] = hist["ALAT"].apply(compact_tool_key)
        hist["ALAT_CODE_KEY"] = hist["ALAT"].apply(tool_code_key)
        hist["ALAT_MOLD_KEY"] = hist["ALAT"].apply(tool_mold_key)
        hist["TIP_NORM"] = hist["TIP_ZAPISA"].apply(_tip_zapisa_norm)
        for alat_key, group in hist.groupby("ALAT_KEY"):
            latest[alat_key] = _izaberi_glavni(group)
        # Fallback za slučaj da je u istoriji upisano samo M1108 ili naziv ima drugačiji format.
        for code_key, group in hist[hist["ALAT_CODE_KEY"].astype(str).str.strip() != ""].groupby("ALAT_CODE_KEY"):
            latest_by_code[code_key] = _izaberi_glavni(group)
        for mold_key, group in hist[hist["ALAT_MOLD_KEY"].astype(str).str.strip() != ""].groupby("ALAT_MOLD_KEY"):
            latest_by_mold[mold_key] = _izaberi_glavni(group)
    rows = []
    for _, r in total_punch_df.iterrows():
        alat = normalize_tool_name(r.get("ALAT", ""))
        if not alat:
            continue
        lifetime = float(to_number(r.get("LIFETIME_UDARCI", 0)))
        interval, zona, pct = preventive_interval_for_lifetime(lifetime)
        last = latest.get(compact_tool_key(alat))
        if last is None:
            last = latest_by_code.get(tool_code_key(alat))
        if last is None:
            last = latest_by_mold.get(tool_mold_key(alat))
        if last is None:
            rows.append({"ALAT": alat, "LIFETIME_UDARCI": lifetime, "ZONA_ZIVOTA": zona, "PROCENAT_ZIVOTA": pct * 100, "INTERVAL_PREVENTIVE": interval, "POSLEDNJA_PREVENTIVA_DATUM": "", "POSLEDNJA_PREVENTIVA_UDARCI": 0, "UDARCI_OD_PREVENTIVE": 0, "OSTALO_DO_PREVENTIVE": interval, "PREKORACENJE": 0, "STATUS_PREVENTIVE": "⚪ Postavi početno stanje", "OPIS_POSLEDNJE": "Nema upisane preventive / početnog stanja"})
            continue
        last_life = float(to_number(last.get("LIFETIME_UDARCI", 0)))
        datum_prev_raw = last.get("DATUM", "")
        tip_last = _tip_zapisa_norm(last.get("TIP_ZAPISA", ""))

        punches_since = None
        if tip_last == "POCETNO_STANJE":
            # Početno stanje: upisani broj je baza za brojanje. Sama činjenica da
            # zapis POSTOJI znači da je stanje postavljeno - broj sme da bude i 0
            # (znači "kreni od nule"), pa se svejedno računa: udarci od preventive
            # = trenutni lifetime - baza.
            punches_since = max(lifetime - last_life, 0)
        else:
            # PREVENTIVA (ili nepoznat tip sa datumom): MERODAVNI su STVARNI dnevni
            # udarci posle datuma preventive - tačno ono što se ručno sabira u tabeli.
            # Ne oslanjamo se na upisani lifetime broj jer Total punch i zbir dnevnih
            # tabova ne moraju savršeno da se poklope, pa bi baza mogla da odstupa.
            dnevni_posle = udarci_posle_datuma(alat, datum_prev_raw)
            if dnevni_posle is not None:
                punches_since = max(float(dnevni_posle), 0)
                # Bazu za prikaz uskladi sa lifetime-om da kartica bude konzistentna.
                last_life = max(lifetime - punches_since, 0)
            elif last_life > 0:
                # Nema dnevnih podataka za taj alat/datum -> rezerva na upisani broj.
                punches_since = max(lifetime - last_life, 0)

        if punches_since is None:
            rows.append({"ALAT": alat, "LIFETIME_UDARCI": lifetime, "ZONA_ZIVOTA": zona, "PROCENAT_ZIVOTA": pct * 100, "INTERVAL_PREVENTIVE": interval, "POSLEDNJA_PREVENTIVA_DATUM": "", "POSLEDNJA_PREVENTIVA_UDARCI": 0, "UDARCI_OD_PREVENTIVE": 0, "OSTALO_DO_PREVENTIVE": interval, "PREKORACENJE": 0, "STATUS_PREVENTIVE": "⚪ Postavi početno stanje", "OPIS_POSLEDNJE": "Preventiva/početno stanje nema upotrebljiv broj udaraca ni datum sa dnevnim podacima"})
            continue

        punches_since = max(float(punches_since), 0)
        remaining = interval - punches_since
        overdue = max(punches_since - interval, 0)
        if lifetime > TOOL_LIFE_PUNCHES:
            status = "⚫ Prešao životni vek"
        elif punches_since >= interval:
            status = "🔴 Za preventivu"
        elif punches_since >= interval * PREVENTIVE_WARNING_RATIO:
            status = "🟡 Blizu preventive"
        else:
            status = "🟢 OK"
        datum_last = last.get("DATUM", "")
        if pd.notna(datum_last) and datum_last != "":
            try:
                datum_last = pd.to_datetime(datum_last).strftime("%d.%m.%Y")
            except Exception:
                datum_last = str(datum_last)
        else:
            datum_last = ""
        rows.append({"ALAT": alat, "LIFETIME_UDARCI": lifetime, "ZONA_ZIVOTA": zona, "PROCENAT_ZIVOTA": pct * 100, "INTERVAL_PREVENTIVE": interval, "POSLEDNJA_PREVENTIVA_DATUM": datum_last, "POSLEDNJA_PREVENTIVA_UDARCI": last_life, "UDARCI_OD_PREVENTIVE": punches_since, "OSTALO_DO_PREVENTIVE": max(remaining, 0), "PREKORACENJE": overdue, "STATUS_PREVENTIVE": status, "OPIS_POSLEDNJE": str(last.get("OPIS", ""))[:250]})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    status_order = {"🔴 Za preventivu": 0, "🟡 Blizu preventive": 1, "⚪ Postavi početno stanje": 2, "⚫ Prešao životni vek": 3, "🟢 OK": 4}
    out["STATUS_ORDER"] = out["STATUS_PREVENTIVE"].map(status_order).fillna(9)
    out = out.sort_values(["STATUS_ORDER", "OSTALO_DO_PREVENTIVE", "LIFETIME_UDARCI"], ascending=[True, True, False])
    return out.reset_index(drop=True)


# =========================================================
# PREDIKTIVNO ODRŽAVANJE
# =========================================================
# Ideja: ako se isti tip kvara na nekom alatu ponovi 3+ puta, i to u proseku na
# manje od PRAG udaraca (podrazumevano 2.500.000), verovatno je reč o delu koji se
# habajući troši u pravilnom ritmu. Program tada računa prosečan razmak (u udarcima)
# između pojavljivanja tog kvara i predviđa kada se očekuje sledeći.
PREDIKTIVNI_PRAG_UDARACA = 2_500_000
PREDIKTIVNI_MIN_PONAVLJANJA = 3

def build_prediktivno(kvarovi_df, udarci_dnevno_df,
                      prag=PREDIKTIVNI_PRAG_UDARACA, min_pon=PREDIKTIVNI_MIN_PONAVLJANJA):
    kolone = ["ALAT", "KVAR", "BROJ_PONAVLJANJA", "PROSECAN_INTERVAL", "POSLEDNJI_DATUM",
              "UDARCI_OD_POSLEDNJEG", "OSTALO_DO_OCEKIVANOG", "STATUS", "PRIMER_OPISA"]
    prazno = pd.DataFrame(columns=kolone)
    if kvarovi_df is None or kvarovi_df.empty or "ALAT" not in kvarovi_df.columns or "DATUM" not in kvarovi_df.columns:
        return prazno
    if udarci_dnevno_df is None or udarci_dnevno_df.empty:
        return prazno

    # Dnevni udarci sa ključevima alata (za pretvaranje datuma u broj udaraca).
    dn = udarci_dnevno_df.copy()
    dn["DATUM"] = pd.to_datetime(dn["DATUM"], errors="coerce").dt.normalize()
    dn["UDARCI"] = pd.to_numeric(dn["UDARCI"], errors="coerce").fillna(0)
    dn = dn.dropna(subset=["DATUM"])
    dn["AK"] = dn["ALAT"].apply(compact_tool_key)
    dn["CK"] = dn["ALAT"].apply(tool_code_key)
    dn["MK"] = dn["ALAT"].apply(tool_mold_key)

    kes_kumulativa = {}
    def kumulativa_za_alat(alat):
        ak = compact_tool_key(alat)
        if ak in kes_kumulativa:
            return kes_kumulativa[ak]
        ck = tool_code_key(alat); mk = tool_mold_key(alat)
        sub = dn[dn["AK"] == ak]
        if sub.empty and ck:
            sub = dn[dn["CK"] == ck]
        if sub.empty and mk:
            sub = dn[dn["MK"] == mk]
        rezultat = None if sub.empty else sub.groupby("DATUM")["UDARCI"].sum().sort_index().cumsum()
        kes_kumulativa[ak] = rezultat
        return rezultat

    kv = kvarovi_df.copy()
    kv["DATUM"] = pd.to_datetime(kv["DATUM"], errors="coerce")
    kv = kv.dropna(subset=["DATUM"])
    kv["ALAT_N"] = kv["ALAT"].apply(normalize_tool_name)
    kv = kv[kv["ALAT_N"].astype(str).str.strip() != ""]
    if "KATEGORIJA" not in kv.columns:
        kv["KATEGORIJA"] = "Ostalo"

    rows = []
    for (alat, kategorija), grupa in kv.groupby(["ALAT_N", "KATEGORIJA"]):
        # "Ostalo" nije određen kvar (ne zna se koji deo), pa nije koristan za prognozu.
        if str(kategorija).strip().lower() in ("ostalo", "", "nan", "none"):
            continue
        cum = kumulativa_za_alat(alat)
        if cum is None or cum.empty:
            continue
        prvi_dnevni = cum.index.min()
        # Jedinstveni dani kada se kvar javio, unutar perioda dnevnog praćenja.
        datumi = sorted({pd.Timestamp(d).normalize() for d in grupa["DATUM"]})
        datumi = [d for d in datumi if d >= prvi_dnevni]
        if len(datumi) < min_pon:
            continue

        def life_at(d):
            uzmi = cum.loc[cum.index <= d]
            return float(uzmi.iloc[-1]) if not uzmi.empty else 0.0

        tacke = [life_at(d) for d in datumi]
        intervali = [b - a for a, b in zip(tacke[:-1], tacke[1:]) if (b - a) > 0]
        if len(intervali) < (min_pon - 1):
            continue
        prosecan = sum(intervali) / len(intervali)
        if prosecan <= 0 or prosecan >= prag:
            continue  # samo kvarovi koji se javljaju na < prag udaraca

        zadnji = datumi[-1]
        life_sada = float(cum.iloc[-1])
        od_poslednjeg = max(life_sada - life_at(zadnji), 0)
        ostalo = prosecan - od_poslednjeg
        if ostalo <= 0:
            status = "🔴 Očekivan kvar"
        elif ostalo <= prosecan * 0.2:
            status = "🟡 Blizu"
        else:
            status = "🟢 Prati"

        primer = ""
        if "PROBLEM" in grupa.columns:
            opisi = [str(x).strip() for x in grupa["PROBLEM"] if str(x).strip() and str(x).strip().lower() not in ("nan", "none")]
            if opisi:
                primer = max(opisi, key=len)[:180]

        rows.append({
            "ALAT": alat,
            "KVAR": kategorija,
            "BROJ_PONAVLJANJA": len(datumi),
            "PROSECAN_INTERVAL": int(round(prosecan)),
            "POSLEDNJI_DATUM": pd.Timestamp(zadnji).strftime("%d.%m.%Y"),
            "UDARCI_OD_POSLEDNJEG": int(round(od_poslednjeg)),
            "OSTALO_DO_OCEKIVANOG": int(round(max(ostalo, 0))),
            "STATUS": status,
            "PRIMER_OPISA": primer,
        })

    if not rows:
        return prazno
    out = pd.DataFrame(rows)
    red = {"🔴 Očekivan kvar": 0, "🟡 Blizu": 1, "🟢 Prati": 2}
    out["_R"] = out["STATUS"].map(red).fillna(9)
    out = out.sort_values(["_R", "OSTALO_DO_OCEKIVANOG", "PROSECAN_INTERVAL"], ascending=[True, True, True]).drop(columns="_R")
    return out.reset_index(drop=True)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_kvarove():
    content = download_bytes(CSV_URL_KVAROVI)
    df = pd.read_csv(BytesIO(content))
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed", case=False)]
    df.columns = [str(c).strip() for c in df.columns]

    rename_map = {}
    mappings = {
        "PROBLEM": ["PROBLEM", "OPIŠI PROBLEM", "OPISI PROBLEM"],
        "RESENJE": ["REŠENJE", "RESENJE", "OPIŠI REŠENJE", "OPISI RESENJE", "OPIŠI REŠENJE PROBLEMA"],
        "DATUM": ["DATUM", "DATE", "VREME", "TIMESTAMP", "VREMENSKA OZNAKA"],
        "ALAT": ["ALAT", "TOOL", "KALUP"],
        "SMENA": ["SMENA", "SHIFT"],
        "TRAJANJE_RAW": ["TRAJANJE", "TRAJANJE ZASTOJA", "TRAJANJE ZASTOJA MIN", "TRAJANJE KVARA", "VREME ZASTOJA"],
        "STATUS": ["STATUS", "STANJE"],
        "PRIORITET": ["PRIORITET", "HITNOST"],
    }
    for standard, candidates in mappings.items():
        col = find_col(df, candidates)
        if col:
            rename_map[col] = standard
    df = df.rename(columns=rename_map)

    for col in ["ALAT", "PROBLEM", "RESENJE", "SMENA", "STATUS", "PRIORITET"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    if "DATUM" in df.columns:
        df["DATUM"] = pd.to_datetime(df["DATUM"], errors="coerce", dayfirst=True)
    df["TRAJANJE"] = df["TRAJANJE_RAW"].apply(trajanje_u_minute) if "TRAJANJE_RAW" in df.columns else 0.0
    if "PROBLEM" in df.columns:
        df["KATEGORIJA"] = df["PROBLEM"].apply(klasifikuj_kvar)
    else:
        df["PROBLEM"] = ""
        df["KATEGORIJA"] = "Ostalo"
    if "STATUS" not in df.columns:
        df["STATUS"] = "Završeno"
    df["STATUS"] = df["STATUS"].replace(["nan", "None", "NaT"], "").fillna("")
    df["STATUS_KANBAN"] = df["STATUS"].apply(normalizuj_status_kvara)
    if "PRIORITET" not in df.columns:
        df["PRIORITET"] = "Normalno"
    return df


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_delove_raw_sheet() -> pd.DataFrame:
    """Učitava tab BAZA A što pouzdanije.
    XLSX je sigurniji od CSV/gviz za tabove sa razmacima u nazivu i za tabele koje imaju uvodne/prazne redove.
    """
    try:
        content = download_bytes(EXCEL_URL_DELOVI)
        excel = pd.ExcelFile(BytesIO(content))
        wanted = norm_col(SHEET_DELOVI)
        sheet_name = None
        for sheet in excel.sheet_names:
            if norm_col(sheet) == wanted:
                sheet_name = sheet
                break
        if sheet_name is None:
            for sheet in excel.sheet_names:
                if wanted in norm_col(sheet) or norm_col(sheet) in wanted:
                    sheet_name = sheet
                    break
        if sheet_name is None:
            sheet_name = excel.sheet_names[0]

        raw = pd.read_excel(excel, sheet_name=sheet_name, header=None, dtype=object)
    except Exception:
        # Fallback ako XLSX iz nekog razloga ne prođe.
        content = download_bytes(CSV_URL_DELOVI)
        raw = pd.read_csv(BytesIO(content), header=None, dtype=object)

    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    if raw.empty:
        return pd.DataFrame()

    keywords = [
        "ID", "ID DELA", "PART", "NAZIV", "NAZIV DELA", "DEO", "STANJE", "KOLICINA", "KOLIČINA",
        "MIN", "MINIMUM", "MINIMALNO", "MAX", "MAKSIMUM", "MAKSIMALNO", "STATUS", "ZALIHE",
        "LOKACIJA", "ORMAR", "FIOKA", "POZICIJA", "PROJECT", "MODEL", "PROJEKAT"
    ]

    best_idx = 0
    best_score = -1
    scan_limit = min(len(raw), 25)
    for idx in range(scan_limit):
        values = [norm_col(v) for v in raw.iloc[idx].tolist() if str(v).strip().lower() not in ["", "nan", "none"]]
        score = 0
        for value in values:
            for key in keywords:
                nk = norm_col(key)
                if value == nk or nk in value or value in nk:
                    score += 1
        # Daj malu prednost redu koji ima više popunjenih ćelija, ali samo kao tie-break.
        score += min(len(values), 10) * 0.05
        if score > best_score:
            best_score = score
            best_idx = idx

    # Ako nismo našli smislen header, uzmi prvi red koji nije prazan.
    if best_score < 1:
        best_idx = 0

    headers = []
    used = {}
    for i, value in enumerate(raw.iloc[best_idx].tolist()):
        name = str(value).strip()
        if name == "" or name.lower() in ["nan", "none"]:
            name = f"KOLONA_{i+1}"
        name = re.sub(r"\s+", " ", name)
        base = name
        if base in used:
            used[base] += 1
            name = f"{base}_{used[base]}"
        else:
            used[base] = 1
        headers.append(name)

    df = raw.iloc[best_idx + 1:].copy()
    df.columns = headers[:len(df.columns)]
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed", case=False)]
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


def direktan_link_slike(url) -> str:
    """Pretvara Google Drive link u direktan link slike koji se prikazuje u aplikaciji.
    Podržava formate: /file/d/ID/view, open?id=ID, uc?id=ID, /d/ID, kao i već gotove
    lh3.googleusercontent.com linkove. Vraća lh3 (Google CDN) verziju, koja je pouzdanija
    za veći broj slika od 'uc?export=view' (koji Drive ograničava pa se učita samo par slika).
    Ako link nije sa Google Drive-a, vraća ga nepromenjenog."""
    u = str(url or "").strip()
    if not u:
        return ""
    fid = ""
    for pattern in (r"/file/d/([A-Za-z0-9_-]{20,})",
                    r"[?&]id=([A-Za-z0-9_-]{20,})",
                    r"lh3\.googleusercontent\.com/d/([A-Za-z0-9_-]{20,})",
                    r"/d/([A-Za-z0-9_-]{20,})"):
        m = re.search(pattern, u)
        if m:
            fid = m.group(1)
            break
    if fid:
        return f"https://lh3.googleusercontent.com/d/{fid}=w600"
    return u


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_delove():
    df = ucitaj_delove_raw_sheet()
    if df.empty:
        return pd.DataFrame()

    # Fleksibilno prepoznavanje kolona iz taba BAZA A.
    col_part_id = find_col(df, [
        "ID DELA", "ID_DELA", "PART_ID", "PART ID", "ID", "SIFRA", "ŠIFRA", "SIFRA DELA", "ŠIFRA DELA", "KOD", "CODE"
    ])
    col_naziv = find_col(df, [
        "NAZIV DELA", "NAZIV", "DEO", "IME DELA", "PART", "PART NAME", "NAME", "ARTIKAL", "NAZIV ARTIKLA", "OPIS DELA"
    ])
    col_pozicija = find_col(df, [
        "POZICIJA", "POSITION", "POZICIJA DELA", "POZICIJA U FIOCI", "MESTO", "MJESTO"
    ])
    col_model = find_col(df, [
        "PROJECT MODEL", "PROJECT/MODEL", "PROJECT_MODEL", "PROJEKAT MODEL", "PROJEKAT", "MODEL", "PROJECT", "MACHINE", "MASINA", "MAŠINA"
    ])
    col_stanje = find_col(df, [
        "STANJE", "TRENUTNO STANJE", "KOLICINA", "KOLIČINA", "KOLICINA NA STANJU", "KOLIČINA NA STANJU", "QTY", "QUANTITY", "ZALIHA", "STANJE ZALIHE", "BROJ KOMADA", "KOMADA"
    ])
    col_min = find_col(df, [
        "MINIMALNO STANJE", "MINIMUM", "MIN", "MIN STANJE", "MINIMALNA KOLICINA", "MINIMALNA KOLIČINA", "MINIMALNA ZALIHA"
    ])
    col_max = find_col(df, [
        "MAKSIMALNO STANJE", "MAKSIMUM", "MAX", "MAKS", "MAX STANJE", "MAKSIMALNA KOLICINA", "MAKSIMALNA KOLIČINA", "MAKSIMALNA ZALIHA"
    ])
    col_status_zalihe = find_col(df, [
        "STATUS ZALIHE", "STATUS", "STATUS STANJA", "STANJE STATUS", "STANJE ZALIHE", "STOCK STATUS", "STATUS_STANJA"
    ])
    col_lokacija = find_col(df, [
        "LOKACIJA", "LOKACIJE", "LOCATION", "LOKACIJA DELA", "MAGACIN", "MESTO SKLADISTENJA", "MESTO SKLADIŠTENJA"
    ])
    col_ormar = find_col(df, ["ORMAR", "ORMARIC", "ORMARIĆ", "CABINET"])
    col_fioka = find_col(df, ["FIOKA", "LADICA", "DRAWER", "POLICA", "SHELF"])
    col_image = find_col(df, [
        "IMAGE URL", "IMAGE_URL", "SLIKA", "SLIKA URL", "SLIKA_URL", "IMAGE", "FOTO", "PHOTO", "FOTOGRAFIJA", "LINK SLIKE"
    ])
    col_note = find_col(df, ["NAPOMENA", "NOTE", "KOMENTAR", "COMMENT", "OPIS"])

    # Ako naziv nije prepoznat, koristi prvu tekstualnu kolonu koja nije očigledno količina/status/lokacija.
    if col_naziv is None:
        excluded = {c for c in [col_part_id, col_stanje, col_min, col_max, col_status_zalihe, col_lokacija, col_ormar, col_fioka, col_image] if c}
        for col in df.columns:
            if col in excluded:
                continue
            sample = df[col].dropna().astype(str).str.strip()
            sample = sample[sample.str.lower().isin(["", "nan", "none"]) == False]
            if len(sample) > 0:
                col_naziv = col
                break

    out = pd.DataFrame(index=df.index)
    out["PART_ID"] = df[col_part_id].astype(str).str.strip() if col_part_id else ""
    out["NAZIV"] = df[col_naziv].astype(str).str.strip() if col_naziv else ""
    out["POZICIJA"] = df[col_pozicija].astype(str).str.strip() if col_pozicija else ""
    out["PROJECT_MODEL"] = df[col_model].astype(str).str.strip() if col_model else ""
    out["STANJE"] = df[col_stanje].apply(to_number).fillna(0) if col_stanje else 0
    out["MINIMUM"] = df[col_min].apply(to_number).fillna(0) if col_min else 0
    out["MAKSIMUM"] = df[col_max].apply(to_number).fillna(0) if col_max else 0
    out["STATUS_ZALIHE"] = df[col_status_zalihe].astype(str).str.strip() if col_status_zalihe else ""

    if col_lokacija:
        out["LOKACIJA"] = df[col_lokacija].astype(str).str.strip()
    else:
        lok_parts = []
        if col_ormar:
            lok_parts.append(df[col_ormar].astype(str).str.strip())
        if col_fioka:
            lok_parts.append(df[col_fioka].astype(str).str.strip())
        if lok_parts:
            loc = lok_parts[0]
            for part in lok_parts[1:]:
                loc = loc + " / " + part
            out["LOKACIJA"] = loc.str.replace("nan", "", case=False, regex=False).str.strip(" / ")
        else:
            out["LOKACIJA"] = ""

    out["IMAGE_URL"] = df[col_image].astype(str).str.strip() if col_image else ""
    out["NAPOMENA"] = df[col_note].astype(str).str.strip() if col_note else ""

    # Ako naziv nema, nemoj bacati red: koristi ID ili poziciju kao privremeni naziv.
    out["NAZIV"] = out["NAZIV"].replace(["nan", "None", ""], pd.NA)
    out["NAZIV"] = out["NAZIV"].fillna(out["PART_ID"].replace(["nan", "None", ""], pd.NA))
    out["NAZIV"] = out["NAZIV"].fillna(out["POZICIJA"].replace(["nan", "None", ""], pd.NA))
    out["NAZIV"] = out["NAZIV"].fillna("Bez naziva")

    for col in ["PART_ID", "NAZIV", "POZICIJA", "PROJECT_MODEL", "STATUS_ZALIHE", "LOKACIJA", "IMAGE_URL", "NAPOMENA"]:
        out[col] = out[col].astype(str).replace(["nan", "None", "<NA>"], "").str.strip()

    # Ne izbacuj redove samo zato što naziv nije prepoznat; izbacujemo samo potpuno prazne zapise.
    prazne_kolone = ["PART_ID", "NAZIV", "POZICIJA", "LOKACIJA", "PROJECT_MODEL"]
    mask_not_empty = (
        out[prazne_kolone]
        .fillna("")
        .apply(lambda r: "".join(str(x) for x in r).strip(), axis=1)
        != ""
    )
    out = out[mask_not_empty].copy()
    out["KLJUC_DELA"] = out["PART_ID"].where(out["PART_ID"].astype(str).str.strip() != "", out["NAZIV"])
    return out.reset_index(drop=True)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_dokumentaciju_raw_sheet() -> pd.DataFrame:
    """Učitava tab DOKUMENTACIJA iz tabele rezervnih delova/procedura.
    Ako tab ne postoji ili je prazan, vraća prazan DataFrame bez rušenja programa.
    """
    try:
        content = download_bytes(EXCEL_URL_DELOVI)
        excel = pd.ExcelFile(BytesIO(content))
        wanted = norm_col(SHEET_DOKUMENTACIJA)
        sheet_name = None
        for sheet in excel.sheet_names:
            if norm_col(sheet) == wanted:
                sheet_name = sheet
                break
        if sheet_name is None:
            for sheet in excel.sheet_names:
                if wanted in norm_col(sheet) or norm_col(sheet) in wanted:
                    sheet_name = sheet
                    break
        if sheet_name is None:
            return pd.DataFrame()
        raw = pd.read_excel(excel, sheet_name=sheet_name, header=None, dtype=object)
    except Exception:
        return pd.DataFrame()

    raw = raw.dropna(how="all").dropna(axis=1, how="all")
    if raw.empty:
        return pd.DataFrame()

    keywords = [
        "ID", "NAZIV", "NAZIV DOKUMENTA", "PROCEDURA", "KATEGORIJA", "TIP", "LINK", "URL",
        "OPIS", "NAPOMENA", "MASINA", "MAŠINA", "ALAT", "JEZIK", "DATUM", "AKTIVNO", "STATUS"
    ]
    best_idx = 0
    best_score = -1
    scan_limit = min(len(raw), 25)
    for idx in range(scan_limit):
        values = [norm_col(v) for v in raw.iloc[idx].tolist() if str(v).strip().lower() not in ["", "nan", "none"]]
        score = 0
        for value in values:
            for key in keywords:
                nk = norm_col(key)
                if value == nk or nk in value or value in nk:
                    score += 1
        score += min(len(values), 10) * 0.05
        if score > best_score:
            best_score = score
            best_idx = idx
    if best_score < 1:
        best_idx = 0

    headers = []
    used = {}
    for i, value in enumerate(raw.iloc[best_idx].tolist()):
        name = str(value).strip()
        if name == "" or name.lower() in ["nan", "none"]:
            name = f"KOLONA_{i+1}"
        name = re.sub(r"\s+", " ", name)
        base = name
        if base in used:
            used[base] += 1
            name = f"{base}_{used[base]}"
        else:
            used[base] = 1
        headers.append(name)

    df = raw.iloc[best_idx + 1:].copy()
    df.columns = headers[:len(df.columns)]
    df = df.dropna(how="all")
    df = df.loc[:, ~df.columns.astype(str).str.contains("^Unnamed", case=False)]
    df.columns = [str(c).strip() for c in df.columns]
    return df.reset_index(drop=True)


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_dokumentaciju() -> pd.DataFrame:
    df = ucitaj_dokumentaciju_raw_sheet()
    if df.empty:
        return pd.DataFrame(columns=["ID", "NAZIV", "KATEGORIJA", "TIP", "LINK", "OPIS", "ALAT_MASINA", "JEZIK", "DATUM", "AKTIVNO"])

    col_id = find_col(df, ["ID", "DOC ID", "ID DOKUMENTA", "SIFRA", "ŠIFRA"])
    col_naziv = find_col(df, ["NAZIV DOKUMENTA", "NAZIV", "PROCEDURA", "NAZIV PROCEDURE", "DOKUMENT", "IME DOKUMENTA", "TITLE"])
    col_kat = find_col(df, ["KATEGORIJA", "CATEGORY", "GRUPA", "TIP PROCEDURE", "OBLAST"])
    col_tip = find_col(df, ["TIP", "TYPE", "FORMAT", "VRSTA", "FILE TYPE"])
    col_link = find_col(df, ["LINK", "URL", "DRIVE LINK", "GOOGLE DRIVE", "DOKUMENT LINK", "PUTANJA"])
    col_opis = find_col(df, ["OPIS", "NAPOMENA", "KOMENTAR", "DESCRIPTION", "NOTE"])
    col_alat = find_col(df, ["MASINA ALAT", "MAŠINA ALAT", "MASINA", "MAŠINA", "ALAT", "ALAT MASINA", "ALAT MAŠINA", "POVEZAN ALAT", "MACHINE", "TOOL"])
    col_jezik = find_col(df, ["JEZIK", "LANGUAGE"])
    col_datum = find_col(df, ["DATUM", "DATE", "DATUM DOKUMENTA", "DODATO"])
    col_aktivno = find_col(df, ["AKTIVNO", "STATUS", "PRIKAZATI", "ACTIVE"])

    # Ako naziv nije prepoznat, koristi prvu smisleno popunjenu kolonu.
    if col_naziv is None:
        excluded = {c for c in [col_id, col_kat, col_tip, col_link, col_opis, col_alat, col_jezik, col_datum, col_aktivno] if c}
        for col in df.columns:
            if col in excluded:
                continue
            sample = df[col].dropna().astype(str).str.strip()
            sample = sample[~sample.str.lower().isin(["", "nan", "none"])]
            if len(sample) > 0:
                col_naziv = col
                break

    out = pd.DataFrame(index=df.index)
    out["ID"] = df[col_id].astype(str).str.strip() if col_id else ""
    out["NAZIV"] = df[col_naziv].astype(str).str.strip() if col_naziv else ""
    out["KATEGORIJA"] = df[col_kat].astype(str).str.strip() if col_kat else "Procedura"
    out["TIP"] = df[col_tip].astype(str).str.strip() if col_tip else "Word"
    out["LINK"] = df[col_link].astype(str).str.strip() if col_link else ""
    out["OPIS"] = df[col_opis].astype(str).str.strip() if col_opis else ""
    out["ALAT_MASINA"] = df[col_alat].astype(str).str.strip() if col_alat else ""
    out["JEZIK"] = df[col_jezik].astype(str).str.strip() if col_jezik else ""
    out["DATUM"] = df[col_datum].astype(str).str.strip() if col_datum else ""
    out["AKTIVNO"] = df[col_aktivno].astype(str).str.strip() if col_aktivno else "DA"

    for col in out.columns:
        out[col] = out[col].astype(str).replace(["nan", "None", "<NA>"], "").str.strip()

    out["NAZIV"] = out["NAZIV"].replace("", pd.NA)
    out["NAZIV"] = out["NAZIV"].fillna(out["ID"].replace("", pd.NA)).fillna("Dokument bez naziva")
    mask_not_empty = out[["ID", "NAZIV", "LINK", "OPIS", "ALAT_MASINA"]].fillna("").apply(lambda r: "".join(str(x) for x in r).strip(), axis=1) != ""
    return out[mask_not_empty].reset_index(drop=True)



def normalizuj_status_akcije(value) -> str:
    raw = str(value or "").strip()
    norm = strip_accents(raw)
    if norm in ["", "nan", "none", "nat"]:
        return "Za uraditi"
    if any(x in norm for x in ["backlog", "ideja", "plan", "novo", "nova"]):
        return "Backlog"
    if any(x in norm for x in ["za urad", "todo", "to do", "otvor", "nije poc", "nije poč"]):
        return "Za uraditi"
    if any(x in norm for x in ["u toku", "uradu", "rad", "working", "progress", "proces"]):
        return "U toku"
    if any(x in norm for x in ["ceka deo", "ceka del", "parts", "deo", "delovi"]):
        return "Čeka deo"
    if any(x in norm for x in ["ceka kinu", "kina", "china", "kinez"]):
        return "Čeka Kinu"
    if any(x in norm for x in ["test", "provera", "provjera"]):
        return "Testiranje"
    if any(x in norm for x in ["zavrs", "gotov", "done", "closed", "resen", "rijesen"]):
        return "Završeno"
    return raw


def normalizuj_prioritet_akcije(value) -> str:
    norm = strip_accents(value).upper()
    if any(x in norm for x in ["VIS", "HIGH", "HIT", "URGENT", "1"]):
        return "VISOK"
    if any(x in norm for x in ["SRED", "MED", "NORMAL", "2"]):
        return "SREDNJI"
    if any(x in norm for x in ["NIZ", "LOW", "3"]):
        return "NIZAK"
    return "SREDNJI"


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def ucitaj_akcije() -> pd.DataFrame:
    """Učitava stvarne akcije iz taba AKCIJE / AKCIONI PLAN ako postoji.
    Pretražuje više radnih knjiga jer je korisnik tokom rada akcije dodavao u različite Google Sheets fajlove.
    """
    out_cols = ["ID", "NASLOV", "OPIS", "STATUS", "PRIORITET", "ALAT", "ROK", "ODGOVORAN", "IZVOR"]
    sources = [
        ("Kvarovi", EXCEL_URL_KVAROVI),
        ("Delovi", EXCEL_URL_DELOVI),
        ("Udarci", EXCEL_URL_UDARCI),
    ]
    frames = []
    for source_name, url in sources:
        try:
            content = download_bytes(url)
            excel = pd.ExcelFile(BytesIO(content))
            # VAŽNO: uzimamo samo pravi tab sa akcijama (npr. "AKCIJE" / "AKCIONI PLAN"),
            # a NE tabove sa odgovorima iz Google forme, logovima, test i backup unosima.
            # Zbog toga su se u karticama pojavljivali unosi tipa
            # "Promena iz Android aplikacije" i "Probna transakcija".
            # Napomena: naziv taba sa odgovorima forme je često ćirilicom
            # ("Одговори из упитника AKCIJE"). norm_col ukloni ćirilicu i ostane samo
            # "AKCIJE", pa markere proveravamo i na SIROVOM nazivu (velika slova),
            # gde ćirilica ostaje vidljiva.
            iskljuceni_markeri_lat = [
                "ODGOVOR", "UPITNIK", "OBRAZAC", "FORM", "RESPONSE", "RESPONSES",
                "LOG", "ANDROID", "APLIKAC", "PROBA", "PROBNA", "TEST",
                "KOPIJA", "COPY", "ARHIV", "ARCHIVE", "BACKUP", "REZERVA", "STARO", "OLD",
            ]
            iskljuceni_markeri_cir = [
                "ОДГОВОР", "УПИТНИК", "ОБРАЗАЦ", "ФОРМ", "ЛОГ", "АНДРОИД",
                "АПЛИКАЦ", "ПРОБА", "ПРОБНА", "ТЕСТ", "КОПИЈА", "АРХИВ", "СТАРО",
            ]

            def _je_pravi_tab_akcija(sh_name: str) -> bool:
                n = norm_col(sh_name)                     # bez ćirilice, samo A-Z0-9
                raw_upper = str(sh_name).strip().upper()  # zadržava ćirilicu
                if "AKCI" not in n and "ACTION" not in n:
                    return False
                if any(m in raw_upper for m in iskljuceni_markeri_lat):
                    return False
                if any(m in raw_upper for m in iskljuceni_markeri_cir):
                    return False
                return True

            candidates = [sh for sh in excel.sheet_names if _je_pravi_tab_akcija(sh)]
            for sheet_name in candidates:
                try:
                    raw = pd.read_excel(excel, sheet_name=sheet_name, dtype=object)
                    if raw.empty or len(raw.columns) < 2:
                        raw0 = pd.read_excel(excel, sheet_name=sheet_name, header=None, dtype=object)
                        header_idx = None
                        for i in range(min(10, len(raw0))):
                            vals = [norm_col(v) for v in list(raw0.iloc[i].values)]
                            if any("STATUS" in v or "STANJE" in v for v in vals) and any("AKCI" in v or "OPIS" in v or "PROBLEM" in v for v in vals):
                                header_idx = i
                                break
                        if header_idx is not None:
                            raw = pd.read_excel(excel, sheet_name=sheet_name, header=header_idx, dtype=object)
                    if raw.empty:
                        continue
                    raw = raw.loc[:, ~raw.columns.astype(str).str.contains("^Unnamed", case=False)]
                    raw.columns = [str(c).strip() for c in raw.columns]
                    id_col = find_col(raw, ["ID", "BROJ", "RB", "R.B.", "NO"])
                    naslov_col = find_col(raw, ["AKCIJA", "NAZIV AKCIJE", "NASLOV", "ACTION", "ZADATAK", "TASK", "PROBLEM"])
                    opis_col = find_col(raw, ["OPIS", "KOMENTAR", "NAPOMENA", "REŠENJE", "RESENJE", "DESCRIPTION", "COMMENT"])
                    status_col = find_col(raw, ["STATUS", "STANJE", "FAZA"])
                    prioritet_col = find_col(raw, ["PRIORITET", "HITNOST", "PRIORITY"])
                    alat_col = find_col(raw, ["ALAT", "MAŠINA", "MASINA", "TOOL", "KALUP", "PROJEKAT", "PROJECT"])
                    rok_col = find_col(raw, ["ROK", "DUE", "DUE DATE", "DATUM", "PLANIRANI ROK"])
                    odgovoran_col = find_col(raw, ["ODGOVORAN", "NOSILAC", "ZADUŽEN", "ZADUZEN", "PERSON", "OWNER", "KO"])
                    if not naslov_col and not opis_col:
                        continue
                    temp = pd.DataFrame()
                    temp["ID"] = raw[id_col].astype(str).str.strip() if id_col else [f"A-{i+1:03d}" for i in range(len(raw))]
                    temp["NASLOV"] = raw[naslov_col].astype(str).str.strip() if naslov_col else raw[opis_col].astype(str).str.strip()
                    temp["OPIS"] = raw[opis_col].astype(str).str.strip() if opis_col else ""
                    temp["STATUS"] = raw[status_col].apply(normalizuj_status_akcije) if status_col else "Za uraditi"
                    temp["PRIORITET"] = raw[prioritet_col].apply(normalizuj_prioritet_akcije) if prioritet_col else "SREDNJI"
                    temp["ALAT"] = raw[alat_col].astype(str).replace("nan", "").str.strip() if alat_col else ""
                    if rok_col:
                        rok = pd.to_datetime(raw[rok_col], errors="coerce", dayfirst=True)
                        temp["ROK"] = rok.dt.strftime("%d.%m.%Y").fillna(raw[rok_col].astype(str).replace("nan", ""))
                    else:
                        temp["ROK"] = ""
                    temp["ODGOVORAN"] = raw[odgovoran_col].astype(str).replace("nan", "").str.strip() if odgovoran_col else ""
                    temp["IZVOR"] = f"{source_name} / {sheet_name}"
                    mask = temp[["NASLOV", "OPIS", "ALAT"]].fillna("").apply(lambda r: "".join(str(x) for x in r).strip(), axis=1) != ""
                    temp = temp[mask]
                    # Dodatna zaštita: izbaci tehničke/test unose koji nisu prave akcije.
                    junk_fraze = ["promena iz android", "probna transakcija", "test unos", "proba"]
                    spojeno = (temp["NASLOV"].astype(str) + " " + temp["OPIS"].astype(str)).apply(strip_accents)
                    temp = temp[~spojeno.apply(lambda s: any(f in s for f in junk_fraze))]
                    if not temp.empty:
                        frames.append(temp[out_cols])
                except Exception:
                    continue
        except Exception:
            continue
    if not frames:
        return pd.DataFrame(columns=out_cols)
    out = pd.concat(frames, ignore_index=True)
    out = out.replace(["nan", "None", "NaT"], "")
    out["ID"] = out["ID"].replace("", pd.NA)
    out["ID"] = out["ID"].fillna(pd.Series([f"A-{i+1:03d}" for i in range(len(out))]))
    return out.reset_index(drop=True)

# =========================================================
# GLAVNO UČITAVANJE
# =========================================================
try:
    with st.spinner("Učitavam podatke iz Google tabela..."):
        udarci, sheetovi = ucitaj_udarce()
        udarci_dnevno = ucitaj_udarce_dnevno()
        total_punch_lifetime = ucitaj_total_punch_lifetime()
        # Preventiva mora da prikaže i alate koji postoje u mesečnim tabovima, ali imaju 0 udaraca
        # ili im je Total punch ćelija prazna/#ERROR.
        total_punch_lifetime = dopuni_total_punch_sa_svim_alatima(total_punch_lifetime, udarci)
        preventiva_istorija = ucitaj_preventiva_istorija()
        kvarovi = ucitaj_kvarove()
        delovi = ucitaj_delove()
        dokumentacija = ucitaj_dokumentaciju()
        akcije = ucitaj_akcije()
except Exception as exc:
    st.error("Greška pri učitavanju podataka. Proveri da li su Google Sheets linkovi dostupni za čitanje.")
    st.exception(exc)
    st.stop()

# =========================================================
# ZAGLAVLJE PROGRAMA (logo, naziv, alarm zvono, kreator)
# =========================================================
# Alarm u zaglavlju koristi kompletno stanje preventive, nezavisno od trenutnih filtera.
preventiva_header_status = build_preventiva_status(total_punch_lifetime, preventiva_istorija, udarci_dnevno)
alarm_prekoracili = preventiva_header_status[preventiva_header_status["STATUS_PREVENTIVE"] == "🔴 Za preventivu"]["ALAT"].astype(str).tolist() if not preventiva_header_status.empty else []
alarm_blizu = preventiva_header_status[preventiva_header_status["STATUS_PREVENTIVE"] == "🟡 Blizu preventive"]["ALAT"].astype(str).tolist() if not preventiva_header_status.empty else []
alarm_total = len(alarm_prekoracili) + len(alarm_blizu)

if alarm_total > 0:
    st.markdown(
        f"""
        <style>
        #header-alert-row + div[data-testid="stHorizontalBlock"] > div:nth-child(3) {{ --alarm-count: "{alarm_total}"; }}
        #header-alert-row + div[data-testid="stHorizontalBlock"] > div:nth-child(3) [data-testid="stPopover"] button::after {{
            content: var(--alarm-count);
            position: absolute;
            top: -7px; right: -7px;
            min-width: 20px; height: 20px;
            padding: 0 4px;
            background: var(--red);
            color: #fff;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 800;
            font-family: 'Inter', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 0 2px var(--bg-1);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

st.markdown('<div id="header-alert-row"></div>', unsafe_allow_html=True)
head_col1, head_col2, head_col3 = st.columns([5.5, 0.65, 2.0], vertical_alignment="center")

with head_col1:
    st.markdown(
        """
        <div class="tower-title-box">
            <div class="tower-title-line">
                <span class="tower-title">Tooling Control Tower</span>
                <span class="live-badge">UŽIVO</span>
            </div>
            <div class="tower-subtitle">Centralni sistem nadzora i upravljanja alatnicom</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with head_col2:
    with st.popover("⚠", width="stretch"):
        st.markdown("**Alarmi preventivnog održavanja**")
        if alarm_total == 0:
            st.success("Trenutno nema aktivnih alarma.")
        else:
            st.caption(f"Ukupno alata u alarmu: {alarm_total}")
            if alarm_prekoracili:
                st.markdown(f"Probili rok za preventivu ({len(alarm_prekoracili)}):")
                st.markdown("".join(f"<div style='color:#ffb4ab; font-weight:700; padding:3px 0;'>● {html.escape(a)}</div>" for a in alarm_prekoracili), unsafe_allow_html=True)
            if alarm_blizu:
                st.markdown(f"Blizu preventive ({len(alarm_blizu)}):")
                st.markdown("".join(f"<div style='color:#ffb77b; font-weight:700; padding:3px 0;'>● {html.escape(a)}</div>" for a in alarm_blizu), unsafe_allow_html=True)

with head_col3:
    st.markdown("""
        <div class="creator-box">
            <div>Kreirao</div>
            <div class="creator-name">Nebojša Đakovački</div>
        </div>
    """, unsafe_allow_html=True)

# Globalni CSS za pokretnu traku alarma.
# Mora biti učitan nezavisno od aktivnog taba, zato nije vezan za CSS Kanban stranice.
st.markdown(
    """
    <style>
    .alarm-strip {
        height: 38px;
        display: flex;
        align-items: center;
        margin: 0 -12px 10px;
        width: calc(100% + 24px);
        border-bottom: 1px solid #404752;
        background: #0a0e14;
        overflow: hidden;
        position: relative;
    }
    .alarm-label {
        height: 38px;
        display: flex;
        align-items: center;
        flex: 0 0 auto;
        padding: 0 15px;
        background: #93000a;
        color: #ffdad6 !important;
        font: 700 10px/38px 'JetBrains Mono', monospace;
        letter-spacing: .5px;
        position: relative;
        z-index: 3;
    }
    .alarm-track {
        flex: 1 1 auto;
        min-width: 0;
        height: 38px;
        overflow: hidden;
        white-space: nowrap;
        position: relative;
        color: #bfc7d4;
        font: 500 10px/38px 'JetBrains Mono', monospace;
    }
    .alarm-marquee {
        position: absolute;
        top: 0;
        left: 0;
        height: 38px;
        display: flex;
        align-items: center;
        width: max-content;
        animation: tct-alarm-scroll 32s linear infinite !important;
        -webkit-animation: tct-alarm-scroll 32s linear infinite !important;
        will-change: transform;
    }
    .alarm-set {
        display: inline-flex;
        align-items: center;
        flex: 0 0 auto;
        padding-left: 36px;
        padding-right: 72px;
    }
    .alarm-strip:hover .alarm-marquee {
        animation-play-state: paused !important;
        -webkit-animation-play-state: paused !important;
    }
    @keyframes tct-alarm-scroll {
        0% { transform: translate3d(0,0,0); }
        100% { transform: translate3d(-50%,0,0); }
    }
    @-webkit-keyframes tct-alarm-scroll {
        0% { -webkit-transform: translate3d(0,0,0); }
        100% { -webkit-transform: translate3d(-50%,0,0); }
    }
    .ticker-sep { margin: 0 22px; color: #404752 !important; }
    .ticker-danger { color: #ffb4ab !important; }
    .ticker-warning { color: #ffb77b !important; }
    .ticker-ok { color: #42d392 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

alarm_ticker_items = []
for alat in alarm_prekoracili[:4]:
    alarm_ticker_items.append(f'<span class="ticker-danger">KRITIČNO: {html.escape(alat)} zahteva preventivu</span>')
for alat in alarm_blizu[:4]:
    alarm_ticker_items.append(f'<span class="ticker-warning">UPOZORENJE: {html.escape(alat)} je blizu preventive</span>')
if not alarm_ticker_items:
    alarm_ticker_items.append('<span class="ticker-ok">SISTEM: Trenutno nema aktivnih alarma preventivnog održavanja</span>')
ticker_html = '<span class="ticker-sep">•</span>'.join(alarm_ticker_items)
# Duplirani sadržaj omogućava neprekidno kružno kretanje bez praznog prekida.
st.markdown(
    '<div class="alarm-strip">'
    '<div class="alarm-label">⚠ AKTIVNI ALARMI</div>'
    '<div class="alarm-track"><div class="alarm-marquee">'
    f'<span class="alarm-set">{ticker_html}</span>'
    f'<span class="alarm-set" aria-hidden="true">{ticker_html}</span>'
    '</div></div></div>',
    unsafe_allow_html=True,
)


# =========================================================
# LEVA NAVIGACIJA + KOMPAKTNI FILTERI U GORNJOJ LINIJI
# =========================================================
PAGE_CONFIG = [
    ("tv-panel", "🖥️", "TV Panel"),
    ("kvarovi", "🧰", "Kvarovi"),
    ("mttr-mtbf", "📊", "MTTR / MTBF"),
    ("preventivno", "🔧", "Preventivno"),
    ("prediktivno", "🔮", "Prediktivno"),
    ("kriticni-alati", "🚨", "Kritični alati"),
    ("rezervni-delovi", "📦", "Rezervni delovi"),
    ("akcije", "🗂️", "Akcije"),
    ("unos-udaraca", "📝", "Unos udaraca"),
    ("udarci-period", "📈", "Udarci po periodu"),
    ("dokumentacija", "📚", "Dokumentacija"),
    ("ai-analiza", "🤖", "AI analiza"),
    ("sirovi-podaci", "🗄️", "Sirovi podaci"),
]

PAGE_LABEL_BY_SLUG = {slug: f"{icon} {label}" for slug, icon, label in PAGE_CONFIG}
requested_page = str(st.query_params.get("page", "tv-panel")).strip().lower()
if requested_page not in PAGE_LABEL_BY_SLUG:
    requested_page = "tv-panel"
selected_page = PAGE_LABEL_BY_SLUG[requested_page]

nav_items = []
for slug, icon, label in PAGE_CONFIG:
    active = " active" if slug == requested_page else ""
    nav_items.append(
        f'<a class="custom-nav-item{active}" href="?page={slug}" target="_self">'
        f'<span class="custom-nav-icon">{icon}</span>'
        f'<span class="custom-nav-label">{html.escape(label)}</span>'
        f'</a>'
    )

st.markdown(
    f"""
    <nav class="custom-left-nav">
        <div class="custom-nav-brand">
            {f'<img class="custom-nav-logo" src="{logo_uri}" alt="Lianbo logo">' if logo_uri else ''}
            <div class="custom-nav-brand-title">Tooling Control</div>
            <div class="custom-nav-brand-subtitle">Sistem upravljanja alatnicom</div>
        </div>
        <div class="custom-nav-list">{''.join(nav_items)}</div>
        <div class="custom-nav-footer">● Sistem povezan<br>Režim: alatnica</div>
    </nav>
    """,
    unsafe_allow_html=True,
)

meseci_default = sheetovi[-3:] if len(sheetovi) >= 3 else sheetovi
lista_alata = sorted(set(udarci.get("ALAT", pd.Series(dtype=str)).dropna().astype(str).unique()).union(
    set(kvarovi.get("ALAT", pd.Series(dtype=str)).dropna().astype(str).unique()),
    set(total_punch_lifetime.get("ALAT", pd.Series(dtype=str)).dropna().astype(str).unique())
))
lista_alata = [a for a in lista_alata if a and a.lower() != "nan"]

if "DATUM" in kvarovi.columns and kvarovi["DATUM"].notna().any():
    min_date = kvarovi["DATUM"].dropna().min().date()
    max_date = kvarovi["DATUM"].dropna().max().date()
else:
    min_date = None
    max_date = None

# Kompaktni filteri u jednoj liniji. Svaki filter se otvara u svom padajućem
# panelu i nakon izbora može odmah da se zatvori klikom van panela.
svi_meseci = st.session_state.get("filter_all_months", False)
meseci_selection = st.session_state.get("filter_months", meseci_default)
svi_alati = st.session_state.get("filter_all_tools", True)
alati_selection = st.session_state.get("filter_tools", [])
period = st.session_state.get("filter_date_range", (min_date, max_date) if min_date is not None and max_date is not None else None)

izabrani_meseci_preview = sheetovi if svi_meseci else (meseci_selection or meseci_default)
izabrani_alati_preview = lista_alata if svi_alati else alati_selection
meseci_label = "Meseci: svi" if svi_meseci else f"Meseci: {len(izabrani_meseci_preview)}"
alati_label = "Alati: svi" if svi_alati else f"Alati: {len(izabrani_alati_preview)}"
if period and isinstance(period, (tuple, list)) and len(period) == 2:
    period_label = f"Period: {pd.to_datetime(period[0]).strftime('%d.%m.%Y')} – {pd.to_datetime(period[1]).strftime('%d.%m.%Y')}"
else:
    period_label = "Period: svi datumi"

filter_month_col, filter_tool_col, filter_date_col, refresh_col = st.columns([1.15, 1.15, 2.15, 0.85], vertical_alignment="center")

with filter_month_col:
    with st.popover(f"▦ {meseci_label}", width="stretch"):
        st.markdown("##### Meseci udaraca")
        svi_meseci = st.checkbox("Svi meseci", value=svi_meseci, key="filter_all_months")
        meseci_selection = st.multiselect(
            "Izaberi mesece",
            sheetovi,
            default=[] if svi_meseci else [m for m in meseci_selection if m in sheetovi],
            disabled=svi_meseci,
            key="filter_months",
            placeholder="Izaberi jedan ili više meseci",
        )
        st.caption("Izbor se primenjuje odmah. Klikni van prozora da ga zatvoriš.")

with filter_tool_col:
    with st.popover(f"⌁ {alati_label}", width="stretch"):
        st.markdown("##### Alati")
        svi_alati = st.checkbox("Svi alati", value=svi_alati, key="filter_all_tools")
        alati_selection = st.multiselect(
            "Izaberi alate",
            lista_alata,
            default=[] if svi_alati else [a for a in alati_selection if a in lista_alata],
            disabled=svi_alati,
            key="filter_tools",
            placeholder="Izaberi jedan ili više alata",
        )
        st.caption("Izbor se primenjuje odmah. Klikni van prozora da ga zatvoriš.")

with filter_date_col:
    with st.popover(f"◫ {period_label}", width="stretch"):
        st.markdown("##### Period kvarova")
        if min_date is not None and max_date is not None:
            period = st.date_input(
                "Izaberi početni i krajnji datum",
                value=period if period else (min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="filter_date_range",
                help="Klikni početni i krajnji datum u kalendaru.",
            )
        else:
            period = None
            st.info("Nema validnih datuma u tabeli kvarova.")
        st.caption("Izbor se primenjuje odmah. Klikni van prozora da ga zatvoriš.")

with refresh_col:
    if st.button("🔄 Osveži", width="stretch", help="Obriši keš i ponovo učitaj Google Sheets podatke"):
        st.cache_data.clear()
        st.rerun()

izabrani_meseci = sheetovi if svi_meseci else (meseci_selection or meseci_default)
izabrani_alati = lista_alata if svi_alati else alati_selection

if period and isinstance(period, (tuple, list)) and len(period) == 2:
    period_txt = f"{pd.to_datetime(period[0]).strftime('%d.%m.%Y')} – {pd.to_datetime(period[1]).strftime('%d.%m.%Y')}"
else:
    period_txt = "svi dostupni datumi"

st.markdown(
    f'<div class="active-filter-strip">'
    f'<span>Meseci <b>{"svi" if svi_meseci else len(izabrani_meseci)}</b></span>'
    f'<span>Alati <b>{"svi" if svi_alati else len(izabrani_alati)}</b></span>'
    f'<span>Period <b>{html.escape(period_txt)}</b></span>'
    f'</div>',
    unsafe_allow_html=True,
)

st.markdown(f'<div class="active-page-strip">Aktivni modul: <b>{html.escape(selected_page)}</b></div>', unsafe_allow_html=True)

# =========================================================
# FILTRIRANJE I IZRAČUNAVANJE
# =========================================================
udarci_f = udarci.copy()
if izabrani_meseci:
    udarci_f = udarci_f[udarci_f["MESEC"].isin(izabrani_meseci)]
if izabrani_alati:
    udarci_f = udarci_f[udarci_f["ALAT"].isin(izabrani_alati)]

kvarovi_f = kvarovi.copy()
if izabrani_alati and "ALAT" in kvarovi_f.columns:
    kvarovi_f = kvarovi_f[kvarovi_f["ALAT"].isin(izabrani_alati)]
if period and isinstance(period, tuple) and len(period) == 2 and "DATUM" in kvarovi_f.columns:
    date_from = pd.to_datetime(period[0])
    date_to = pd.to_datetime(period[1]) + pd.Timedelta(days=1)
    kvarovi_f = kvarovi_f[(kvarovi_f["DATUM"] >= date_from) & (kvarovi_f["DATUM"] < date_to)]

ukupno_udarci = udarci_f.groupby("ALAT", as_index=False)["UDARCI"].sum().sort_values("UDARCI", ascending=False) if not udarci_f.empty else pd.DataFrame(columns=["ALAT", "UDARCI"])

if not kvarovi_f.empty and "ALAT" in kvarovi_f.columns:
    kvarovi_po_alatu = kvarovi_f.groupby("ALAT", as_index=False).agg(
        BROJ_KVAROVA=("ALAT", "count"),
        ZASTOJ_MIN=("TRAJANJE", "sum"),
        MTTR_MIN=("TRAJANJE", "mean"),
    )
else:
    kvarovi_po_alatu = pd.DataFrame(columns=["ALAT", "BROJ_KVAROVA", "ZASTOJ_MIN", "MTTR_MIN"])

analitika = ukupno_udarci.merge(kvarovi_po_alatu, on="ALAT", how="outer").fillna(0)
if not analitika.empty:
    analitika["KVAROVA_NA_1M_UDARACA"] = analitika.apply(lambda r: (r["BROJ_KVAROVA"] / r["UDARCI"] * 1_000_000) if r["UDARCI"] > 0 else 0, axis=1)
    analitika["STATUS"] = analitika["KVAROVA_NA_1M_UDARACA"].apply(lambda v: "🔴 Kritično" if v >= 3 else ("🟡 Praćenje" if v >= 1 else "🟢 OK"))
    analitika = analitika.sort_values(["BROJ_KVAROVA", "KVAROVA_NA_1M_UDARACA", "ZASTOJ_MIN"], ascending=False)

ukupno_kvarova = len(kvarovi_f)
ukupno_zastoj = float(kvarovi_f["TRAJANJE"].sum()) if "TRAJANJE" in kvarovi_f.columns and not kvarovi_f.empty else 0.0
mttr_ukupno = ukupno_zastoj / ukupno_kvarova if ukupno_kvarova else 0.0
ukupno_udaraca = int(udarci_f["UDARCI"].sum()) if not udarci_f.empty else 0
kriticni_broj = int((analitika["STATUS"] == "🔴 Kritično").sum()) if not analitika.empty else 0

def status_zalihe_po_pravilima(row):
    if row["UKUPNO_STANJE"] <= 0:
        return "🔴 Nema"
    if row["MINIMUM"] > 0 and row["UKUPNO_STANJE"] < row["MINIMUM"]:
        return "🟡 Ispod minimuma"
    if row.get("MAKSIMUM", 0) > 0 and row["UKUPNO_STANJE"] > row["MAKSIMUM"]:
        return "🔵 Preko maksimuma"
    return "🟢 OK"

if not delovi.empty:
    delovi_zero = delovi[delovi["STANJE"] <= 0]
    grupisani_delovi = delovi.groupby("KLJUC_DELA", as_index=False).agg(
        PART_ID=("PART_ID", "first"),
        NAZIV=("NAZIV", "first"),
        UKUPNO_STANJE=("STANJE", "sum"),
        MINIMUM=("MINIMUM", "max"),
        MAKSIMUM=("MAKSIMUM", "max"),
        BROJ_LOKACIJA=("LOKACIJA", "nunique"),
        LOKACIJE=("LOKACIJA", lambda x: ", ".join(sorted(set([str(v) for v in x if str(v).strip() and str(v).lower() != "nan"])))[:500]),
        PROJECT_MODEL=("PROJECT_MODEL", lambda x: ", ".join(sorted(set([str(v) for v in x if str(v).strip() and str(v).lower() != "nan"])))[:300]),
        STATUS_IZ_TABELE=("STATUS_ZALIHE", lambda x: ", ".join(sorted(set([str(v) for v in x if str(v).strip() and str(v).lower() not in ["nan", "none"]])))[:200]),
        IMAGE_URL=("IMAGE_URL", lambda x: next((str(v) for v in x if str(v).startswith("http")), "")),
    ).sort_values(["UKUPNO_STANJE", "NAZIV"], ascending=[True, True])
    grupisani_delovi["STATUS"] = grupisani_delovi.apply(status_zalihe_po_pravilima, axis=1)
    delovi_min = grupisani_delovi[(grupisani_delovi["MINIMUM"] > 0) & (grupisani_delovi["UKUPNO_STANJE"] < grupisani_delovi["MINIMUM"])]
    delovi_max = grupisani_delovi[(grupisani_delovi["MAKSIMUM"] > 0) & (grupisani_delovi["UKUPNO_STANJE"] > grupisani_delovi["MAKSIMUM"])]
else:
    delovi_zero = pd.DataFrame()
    delovi_min = pd.DataFrame()
    delovi_max = pd.DataFrame()
    grupisani_delovi = pd.DataFrame()


# Preventivno održavanje - trenutni status
preventiva_status = build_preventiva_status(total_punch_lifetime, preventiva_istorija, udarci_dnevno)
if izabrani_alati and not preventiva_status.empty:
    preventiva_status_f = preventiva_status[preventiva_status["ALAT"].isin(izabrani_alati)].copy()
else:
    preventiva_status_f = preventiva_status.copy()

preventiva_za_broj = int((preventiva_status_f["STATUS_PREVENTIVE"] == "🔴 Za preventivu").sum()) if not preventiva_status_f.empty else 0
preventiva_blizu_broj = int((preventiva_status_f["STATUS_PREVENTIVE"] == "🟡 Blizu preventive").sum()) if not preventiva_status_f.empty else 0
preventiva_nepostavljena_broj = int((preventiva_status_f["STATUS_PREVENTIVE"] == "⚪ Postavi početno stanje").sum()) if not preventiva_status_f.empty else 0

# =========================================================
# UPIS UDARACA U GOOGLE SHEETS PREKO APPS SCRIPT-A
# =========================================================
def load_local_config():
    """Učitava lokalni config.json iz istog foldera gde je app.py."""
    default_config = {"apps_script_url": ""}
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                default_config.update(data)
    except Exception:
        pass
    return default_config


def save_local_config(config: dict):
    """Čuva lokalni config.json. Ako fajl ne postoji, napraviće ga."""
    safe_config = {"apps_script_url": str(config.get("apps_script_url", "")).strip()}
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(safe_config, f, ensure_ascii=False, indent=2)


# ---- Skladište broja smena po danu i alatu (za MTBF / opening time) ----
# Čuva se u zasebnom smene.json (ne dira config.json). Ključ je "DATUM|ključ_alata",
# pa je nezavisno od tačnog formata naziva alata.
def smena_kljuc(datum, alat) -> str:
    try:
        d = pd.to_datetime(datum).date()
    except Exception:
        d = str(datum)
    return f"{d}|{compact_tool_key(alat)}"


def load_smene() -> dict:
    try:
        if SMENE_FILE.exists():
            with open(SMENE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def save_smena(datum, alat, broj_smena) -> bool:
    try:
        data = load_smene()
        data[smena_kljuc(datum, alat)] = int(broj_smena)
        with open(SMENE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def izracunaj_operating_minute(udarci_dnevno_df, period=None, alati=None):
    """Vreme rada (u minutima) po alatu i ukupno.
    Radni dan = dan kada je alat imao > 0 udaraca. Za taj dan vreme rada je
    (broj smena tog dana) × 410 min. Broj smena se čita iz smene.json; ako za taj
    dan/alat nije upisan, podrazumeva se 2 smene (kako je i dogovoreno za stare dane).
    Vraća: (dict ključ_alata -> minuti, ukupno_minuta)."""
    if udarci_dnevno_df is None or udarci_dnevno_df.empty or not {"DATUM", "ALAT", "UDARCI"}.issubset(udarci_dnevno_df.columns):
        return {}, 0.0
    dn = udarci_dnevno_df.copy()
    dn["DATUM"] = pd.to_datetime(dn["DATUM"], errors="coerce")
    dn["UDARCI"] = pd.to_numeric(dn["UDARCI"], errors="coerce").fillna(0)
    dn = dn.dropna(subset=["DATUM"])
    dn = dn[dn["UDARCI"] > 0]
    if alati:
        dn = dn[dn["ALAT"].isin(alati)]
    if period and isinstance(period, tuple) and len(period) == 2:
        d0 = pd.to_datetime(period[0]); d1 = pd.to_datetime(period[1]) + pd.Timedelta(days=1)
        dn = dn[(dn["DATUM"] >= d0) & (dn["DATUM"] < d1)]
    if dn.empty:
        return {}, 0.0
    dn["TK"] = dn["ALAT"].apply(compact_tool_key)
    dn["DAN"] = dn["DATUM"].dt.normalize()
    # jedan radni dan po alatu se broji jednom (ako slučajno ima duplih redova)
    dn = dn.drop_duplicates(subset=["TK", "DAN"])
    smene = load_smene()
    def minute_reda(r):
        k = f"{r['DAN'].date()}|{r['TK']}"
        return float(smene.get(k, PODRAZUMEVANE_SMENE)) * SMENA_MINUTA
    dn["OPERATING_MIN"] = dn.apply(minute_reda, axis=1)
    po_alatu = dn.groupby("TK")["OPERATING_MIN"].sum().to_dict()
    return po_alatu, float(dn["OPERATING_MIN"].sum())


def get_apps_script_url():
    try:
        secret_url = st.secrets.get("APPS_SCRIPT_URL", "")
    except Exception:
        secret_url = ""

    config_url = str(load_local_config().get("apps_script_url", "")).strip()
    session_url = str(st.session_state.get("apps_script_url_runtime", "")).strip()

    return str(session_url or config_url or secret_url or APPS_SCRIPT_URL_DEFAULT).strip()


def pozovi_apps_script(payload: dict):
    url = get_apps_script_url()
    if not url:
        return {"ok": False, "message": "Apps Script URL nije podešen."}
    try:
        response = requests.post(url, json=payload, timeout=45)
        try:
            data = response.json()
        except Exception:
            return {"ok": False, "message": f"Odgovor nije JSON. HTTP {response.status_code}: {response.text[:500]}"}
        if response.status_code >= 400:
            data["ok"] = False
            data["message"] = data.get("message", f"HTTP greška {response.status_code}")
        return data
    except Exception as e:
        return {"ok": False, "message": str(e)}


def mesec_iz_datuma(datum):
    try:
        return pd.to_datetime(datum).strftime("%m.%Y")
    except Exception:
        return ""

# =========================================================
# SADRŽAJ IZABRANOG MODULA
# =========================================================
if selected_page == '🖥️ TV Panel':
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    with c1: kpi_card("Ukupno kvarova", f"{ukupno_kvarova}", "Izabrani period")
    with c2: kpi_card("Ukupno zastoja", f"{ukupno_zastoj:.0f} min", f"{ukupno_zastoj/60:.1f} h")
    with c3: kpi_card("MTTR", f"{mttr_ukupno:.1f} min", "Prosek intervencije")
    with c4: kpi_card("Udarci", f"{ukupno_udaraca:,}", "Izabrani meseci")
    with c5: kpi_card("Kritični alati", f"{kriticni_broj}", "Kvarovi / 1M ≥ 3")
    with c6: kpi_card("Delovi bez stanja", f"{len(delovi_zero)}", "Stanje ≤ 0")
    with c7: kpi_card("Preventiva", f"{preventiva_za_broj + preventiva_blizu_broj}", "Za / blizu")

    left, right = st.columns([1.15, 0.85])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Top kritični alati")
        if not analitika.empty:
            fig = px.bar(
                analitika.head(10),
                x="ALAT",
                y="KVAROVA_NA_1M_UDARACA",
                color="STATUS",
                text="BROJ_KVAROVA",
                title="Kvarovi na milion udaraca",
                color_discrete_map=STATUS_COLOR_MAP,
            )
            st.plotly_chart(plotly_layout(fig, 500), width="stretch")
        else:
            st.info("Nema dovoljno podataka za kritične alate.")
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Alarmi")
        if not analitika.empty:
            top_alarm = analitika[analitika["STATUS"] == "🔴 Kritično"].head(5)
            if top_alarm.empty:
                st.success("Nema kritičnih alata po trenutnim pravilima.")
            for _, row in top_alarm.iterrows():
                st.markdown(f"""
                    <div class="kanban-item">
                        <div class="kanban-item-title">🔴 {row['ALAT']}</div>
                        <div class="kanban-item-meta">Kvarova: <b>{int(row['BROJ_KVAROVA'])}</b> | Zastoj: <b>{row['ZASTOJ_MIN']:.0f} min</b></div>
                        <div class="kanban-item-meta">Kvarova / 1M: <b>{row['KVAROVA_NA_1M_UDARACA']:.2f}</b></div>
                    </div>
                    """, unsafe_allow_html=True)
        if not delovi_zero.empty:
            st.warning(f"Rezervni delovi bez stanja: {len(delovi_zero)}")
        st.markdown('</div>', unsafe_allow_html=True)

    bottom1, bottom2 = st.columns(2)
    with bottom1:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Trend zastoja")
        if "DATUM" in kvarovi_f.columns and kvarovi_f["DATUM"].notna().any():
            trend = kvarovi_f.dropna(subset=["DATUM"]).copy()
            trend["DAN"] = trend["DATUM"].dt.date
            trend = trend.groupby("DAN", as_index=False).agg(BROJ_KVAROVA=("DAN", "count"), ZASTOJ_MIN=("TRAJANJE", "sum"))
            fig = px.bar(trend, x="DAN", y="ZASTOJ_MIN", text="BROJ_KVAROVA", title="Zastoj po danima")
            st.plotly_chart(plotly_layout(fig, 430), width="stretch")
        else:
            st.info("Nema validnih datuma za trend.")
        st.markdown('</div>', unsafe_allow_html=True)

    with bottom2:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Najčešće kategorije kvarova")
        if not kvarovi_f.empty:
            kat = kvarovi_f.groupby("KATEGORIJA", as_index=False).size().rename(columns={"size": "BROJ"}).sort_values("BROJ", ascending=False)
            fig = px.bar(kat.head(10), x="KATEGORIJA", y="BROJ", text="BROJ", title="Pareto kategorija")
            st.plotly_chart(plotly_layout(fig, 430), width="stretch")
        else:
            st.info("Nema kvarova za izabrani period.")
        st.markdown('</div>', unsafe_allow_html=True)

if selected_page == '🧰 Kvarovi':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Kanban kvarova")
    st.caption("Ako u tabeli kvarova dodaš kolonu STATUS, kartice se automatski raspoređuju. Za stare podatke, bez statusa, prikazuje se 'Završeno'.")

    if "STATUS_KANBAN" not in kvarovi_f.columns and "STATUS" in kvarovi_f.columns:
        kvarovi_f = kvarovi_f.copy()
        kvarovi_f["STATUS_KANBAN"] = kvarovi_f["STATUS"].apply(normalizuj_status_kvara)

    statuses = ["Prijavljeno", "U radu", "Čeka deo", "Čeka Kinu", "Ponovljen kvar", "Završeno"]

    if not kvarovi_f.empty and "STATUS_KANBAN" in kvarovi_f.columns:
        pregled_statusa = kvarovi_f.groupby("STATUS_KANBAN").size().reset_index(name="BROJ")
        st.caption("Prepoznati statusi: " + ", ".join([f"{r.STATUS_KANBAN}: {int(r.BROJ)}" for r in pregled_statusa.itertuples()]))

    # Važno: ceo Kanban renderujemo kao jedan HTML blok.
    # Streamlit ne drži pouzdano otvorene <div> tagove kroz više st.markdown poziva,
    # zbog čega su se u prethodnoj verziji videle prazne kolone, a naslovi su bežali dole.
    # Paleta nijansi za kartice, da svaka kartica ima drugačiju (ali suptilnu) boju pozadine.
    CARD_SHADES = [
        ("linear-gradient(135deg, rgba(41,211,200,0.13), rgba(41,211,200,0.03))", "rgba(41,211,200,0.65)"),
        ("linear-gradient(135deg, rgba(79,168,245,0.13), rgba(79,168,245,0.03))", "rgba(79,168,245,0.65)"),
        ("linear-gradient(135deg, rgba(245,185,66,0.13), rgba(245,185,66,0.03))", "rgba(245,185,66,0.65)"),
        ("linear-gradient(135deg, rgba(167,139,250,0.13), rgba(167,139,250,0.03))", "rgba(167,139,250,0.65)"),
        ("linear-gradient(135deg, rgba(242,96,122,0.13), rgba(242,96,122,0.03))", "rgba(242,96,122,0.65)"),
        ("linear-gradient(135deg, rgba(62,213,152,0.13), rgba(62,213,152,0.03))", "rgba(62,213,152,0.65)"),
        ("linear-gradient(135deg, rgba(240,152,92,0.13), rgba(240,152,92,0.03))", "rgba(240,152,92,0.65)"),
    ]

    kanban_html = ['<div class="kanban-board">']
    for status in statuses:
        if "STATUS_KANBAN" in kvarovi_f.columns and not kvarovi_f.empty:
            data = kvarovi_f[kvarovi_f["STATUS_KANBAN"] == status].head(20)
            count_status = int((kvarovi_f["STATUS_KANBAN"] == status).sum())
        else:
            data = pd.DataFrame()
            count_status = 0

        kanban_html.append('<div class="kanban-col-fixed">')
        kanban_html.append(f'<div class="kanban-title-fixed">{html.escape(status)} <span style="opacity:.75">({count_status})</span></div>')

        if data.empty:
            kanban_html.append('<div class="kanban-empty">Nema kartica</div>')
        else:
            for card_idx, (_, row) in enumerate(data.iterrows()):
                datum_txt = row["DATUM"].strftime("%d.%m.%Y") if "DATUM" in row and pd.notna(row["DATUM"]) else ""
                alat_txt = html.escape(str(row.get("ALAT", "")))
                kategorija_txt = html.escape(str(row.get("KATEGORIJA", "")))
                problem_txt = html.escape(str(row.get("PROBLEM", ""))[:160])
                raw_status = html.escape(str(row.get("STATUS", "")))
                try:
                    trajanje_txt = f"{float(row.get('TRAJANJE', 0)):.0f} min"
                except Exception:
                    trajanje_txt = "0 min"

                shade_bg, shade_border = CARD_SHADES[card_idx % len(CARD_SHADES)]
                kanban_html.append(
                    f'<div class="kanban-item-fixed" style="background:{shade_bg}; border-left-color:{shade_border};">'
                    f'<div class="kanban-item-title">{alat_txt}</div>'
                    f'<div class="kanban-item-meta">{html.escape(datum_txt)} | {kategorija_txt} | {html.escape(trajanje_txt)}</div>'
                    f'<div class="kanban-item-meta">Status iz tabele: <b>{raw_status}</b></div>'
                    f'<div class="kanban-item-meta">{problem_txt}</div>'
                    '</div>'
                )
        kanban_html.append('</div>')
    kanban_html.append('</div>')

    st.markdown("""
    <style>
        .kanban-board {
            display: grid;
            grid-template-columns: repeat(6, minmax(176px, 1fr));
            gap: 12px;
            width: 100%;
            align-items: start;
            margin-top: 16px;
            overflow-x: auto;
        }
        .kanban-col-fixed {
            background: rgba(19, 29, 46, 0.68);
            border: 1px solid rgba(126, 170, 224, 0.22);
            border-radius: 16px;
            padding: 14px;
            min-height: 520px;
            max-height: 680px;
            overflow-y: auto;
            box-shadow: inset 0 0 24px rgba(0,0,0,.20);
        }
        .kanban-title-fixed {
            color: #f4f8fd;
            font-family: 'Space Grotesk', 'Inter', sans-serif;
            font-size: 15.5px;
            font-weight: 700;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(41, 211, 200, 0.28);
            text-transform: uppercase;
            letter-spacing: .3px;
        }
        .kanban-item-fixed {
            background: rgba(255,255,255,0.055);
            border: 1px solid rgba(255,255,255,0.10);
            border-left: 3px solid rgba(41, 211, 200, 0.55);
            border-radius: 12px;
            padding: 11px 12px;
            margin-bottom: 9px;
            color: #c3d0e3;
            transition: border-color .15s ease, background .15s ease;
        }
        .kanban-item-fixed:hover {
            background: rgba(255,255,255,0.09);
            border-left-color: #29d3c8;
        }
        .kanban-item-title {
            color: #f4f8fd;
            font-weight: 700;
            font-size: 13.5px;
            margin-bottom: 4px;
        }
        .kanban-item-meta {
            color: #a9b7cc;
            font-size: 11.5px;
            margin-top: 4px;
            line-height: 1.4;
        }
        .kanban-empty {
            color: #7c8aa0;
            font-size: 13px;
            font-style: italic;
            padding: 10px 4px;
        }
        @media (max-width: 1400px) {
            .kanban-board { grid-template-columns: repeat(3, minmax(210px, 1fr)); }
        }
    
        /* ======================================================
           STITCH FAITHFUL PASS V2 — HIGH-DENSITY CONTROL TOWER
           ====================================================== */
        :root { --left-nav-width:240px; --surface:#0f1419; --surface-deep:#0a0e14; --surface-low:#181c22; --surface-mid:#1c2026; --surface-high:#262a30; --outline-tech:#404752; --text-main:#dfe2ea; --text-muted:#9ca7b5; --primary-tech:#9ecaff; --blue-tech:#2196f3; --orange-tech:#ffb77b; --red-tech:#ffb4ab; --green-tech:#42d392; }
        html, body, .stApp { background:#0f1419 !important; }
        .stApp { background-image:none !important; }
        [data-testid="stHeader"] { height:0 !important; min-height:0 !important; border:0 !important; background:transparent !important; }
        [data-testid="stToolbar"] { top:9px !important; z-index:100002 !important; }
        [data-testid="stMainBlockContainer"], .block-container { padding:0 12px 22px !important; }
        .custom-left-nav { width:240px !important; background:#0f1419 !important; border-right:1px solid #404752 !important; }
        [data-testid="stAppViewContainer"] { padding-left:240px !important; }
        .custom-nav-brand { min-height:80px !important; padding:12px 14px 10px !important; }
        .custom-nav-logo { width:128px !important; max-height:30px !important; margin-bottom:7px !important; }
        .custom-nav-brand-title { font-size:15px !important; }
        .custom-nav-brand-subtitle { font-size:9px !important; }
        .custom-nav-list { padding:8px 4px 74px !important; }
        .custom-nav-item { min-height:42px !important; padding:0 12px !important; gap:10px !important; font-size:12px !important; }
        .custom-nav-icon { width:22px !important; font-size:15px !important; }
        .custom-nav-footer { background:#0a0e14 !important; border-top:1px solid #404752 !important; padding:11px 14px !important; }
        #header-alert-row + div[data-testid="stHorizontalBlock"] { height:64px !important; min-height:64px !important; margin:0 -12px !important; padding:0 16px !important; width:calc(100% + 24px) !important; border-bottom:1px solid #404752 !important; background:#0f1419 !important; align-items:center !important; }
        .tower-title-box { padding:0 !important; margin:0 !important; border:0 !important; background:transparent !important; box-shadow:none !important; text-align:left !important; }
        .tower-title-line { display:flex; align-items:center; gap:12px; }
        .tower-title { font-family:Inter,sans-serif !important; font-size:18px !important; line-height:22px !important; font-weight:600 !important; }
        .tower-subtitle { margin-top:2px !important; font-family:'JetBrains Mono',monospace !important; font-size:9px !important; line-height:12px !important; text-transform:uppercase; letter-spacing:.75px; color:#89919d !important; }
        .live-badge { display:inline-flex; align-items:center; padding:3px 7px; border:1px solid #404752; border-radius:2px; color:#9ecaff; background:#31353b; font:700 9px/11px 'JetBrains Mono',monospace; letter-spacing:.6px; }
        .creator-box { min-height:auto !important; padding:0 34px 0 0 !important; border:0 !important; background:transparent !important; box-shadow:none !important; font:500 9px/12px 'JetBrains Mono',monospace !important; color:#89919d !important; }
        .creator-name { font:600 10px/14px 'JetBrains Mono',monospace !important; }
        #header-alert-row + div [data-testid="stPopover"] > button { width:38px !important; min-width:38px !important; height:38px !important; min-height:38px !important; border-radius:3px !important; background:transparent !important; border:1px solid #404752 !important; font-size:17px !important; box-shadow:none !important; }
        .alarm-strip { height:38px; display:flex; align-items:center; margin:0 -12px 10px; width:calc(100% + 24px); border-bottom:1px solid #404752; background:#0a0e14; overflow:hidden; }
        .alarm-label { height:38px; display:flex; align-items:center; flex:0 0 auto; padding:0 15px; background:#93000a; color:#ffdad6; font:700 10px/38px 'JetBrains Mono',monospace; letter-spacing:.5px; position:relative; z-index:2; }
        .alarm-track { flex:1 1 auto; min-width:0; overflow:hidden; white-space:nowrap; color:#bfc7d4; font:500 10px/38px 'JetBrains Mono',monospace; }
        .alarm-marquee { display:flex; width:max-content; min-width:200%; animation:alarm-scroll 28s linear infinite; will-change:transform; }
        .alarm-set { display:inline-flex; align-items:center; flex:none; padding-left:28px; padding-right:52px; }
        .alarm-strip:hover .alarm-marquee { animation-play-state:paused; }
        @keyframes alarm-scroll { from { transform:translateX(0); } to { transform:translateX(-50%); } }
        .ticker-sep { margin:0 22px; color:#404752; }.ticker-danger{color:#ffb4ab}.ticker-warning{color:#ffb77b}.ticker-ok{color:#42d392}
        div[data-testid="stHorizontalBlock"]:has(.active-filter-strip) { gap:10px !important; margin-bottom:4px !important; }
        .active-filter-strip { min-height:27px; display:flex; align-items:center; gap:22px; padding:0 3px; color:#7f8b9d; font:500 9px/27px 'JetBrains Mono',monospace; text-transform:uppercase; letter-spacing:.35px; white-space:nowrap; overflow:hidden; }
        .active-filter-strip span { color:#7f8b9d !important; }
        .active-filter-strip b { color:#b8c7db !important; font-weight:700; }
        [data-testid="stPopover"] > button, .stButton>button { min-height:42px !important; border-radius:3px !important; box-shadow:none !important; }
        .active-page-strip { margin:7px 0 9px !important; font:500 10px/14px 'JetBrains Mono',monospace !important; }
        .section-card { padding:14px !important; margin-bottom:10px !important; border:1px solid #404752 !important; border-radius:4px !important; background:#181c22 !important; box-shadow:none !important; }
        .kpi-card { min-height:88px !important; padding:12px 13px !important; border:1px solid #404752 !important; border-top:3px solid #2196f3 !important; border-left:1px solid #404752 !important; border-radius:4px !important; background:#1c2026 !important; box-shadow:0 0 14px rgba(33,150,243,.08) !important; }
        .kpi-title { font:600 9px/13px 'JetBrains Mono',monospace !important; letter-spacing:.6px !important; }.kpi-value{font:700 22px/28px 'JetBrains Mono',monospace !important}.kpi-note{font-size:10px!important;margin-top:3px!important}
        [data-testid="stPlotlyChart"] { padding:3px !important; border:1px solid #404752 !important; border-radius:4px !important; background:#181c22 !important; box-shadow:none !important; }
        h2{font-size:19px!important}h3{font-size:16px!important}[data-testid="stDataFrame"]{border:1px solid #404752!important;border-radius:4px!important}
        .module-command-bar { height:48px; display:grid; grid-template-columns:auto minmax(220px,1fr) auto; align-items:center; gap:12px; margin-bottom:12px; padding:0 10px; background:#181c22; border:1px solid #404752; border-radius:4px; }
        .command-tabs{display:flex;gap:5px}.command-tab{padding:6px 10px;color:#89919d;border:1px solid transparent;font:600 10px/13px 'JetBrains Mono',monospace}.command-tab.active{color:#9ecaff;background:#262a30;border-color:#404752}
        .command-search{max-width:310px;height:30px;display:flex;align-items:center;padding:0 10px;color:#89919d;background:#1c2026;border:1px solid #404752;border-radius:3px;font:500 10px 'JetBrains Mono',monospace}.command-primary{justify-self:end;padding:8px 15px;background:#9ecaff;color:#003258;border-radius:3px;font:700 10px 'JetBrains Mono',monospace}
        .actions-kanban{display:grid;grid-template-columns:repeat(4,minmax(220px,1fr));gap:8px;min-height:470px;overflow-x:auto;padding-bottom:6px}.action-column{min-width:220px;background:#0a0e14;border:1px solid #404752;border-radius:4px;overflow:hidden}.action-column-header{height:44px;display:flex;justify-content:space-between;align-items:center;padding:0 11px;border-top:3px solid var(--column-accent);border-bottom:1px solid #404752;color:#dfe2ea;font:600 10px 'JetBrains Mono',monospace;letter-spacing:.55px}.action-column-header b{padding:3px 5px;background:#1c2026;color:#9ecaff;font-size:9px}.action-column-body{padding:9px}.action-card{margin-bottom:9px;padding:11px;background:#1c2026;border:1px solid #404752;border-radius:3px}.action-card-top,.action-card-footer{display:flex;justify-content:space-between;align-items:center;gap:7px}.priority-chip{padding:3px 6px;border-radius:2px;font:700 8px 'JetBrains Mono',monospace}.priority-high{background:#93000a;color:#ffdad6}.priority-medium{background:#db7900;color:#2e1500}.action-id{color:#9ecaff;font:600 9px 'JetBrains Mono',monospace}.action-title{margin:10px 0 6px;color:#dfe2ea;font:600 12px/17px Inter,sans-serif}.action-comment{min-height:30px;color:#9ca7b5;font:400 10px/14px Inter,sans-serif}.action-card-footer{margin-top:10px;padding-top:8px;border-top:1px solid #31353b;color:#bfc7d4;font:500 9px 'JetBrains Mono',monospace}.kanban-empty{padding:22px 8px;color:#657080;text-align:center;font:500 9px 'JetBrains Mono',monospace}.system-status-footer{height:30px;display:flex;justify-content:space-between;align-items:center;margin-top:8px;padding:0 10px;background:#0a0e14;border:1px solid #404752;color:#89919d;font:500 8px 'JetBrains Mono',monospace}.system-status-footer i{display:inline-block;width:6px;height:6px;border-radius:50%;background:#42d392;box-shadow:0 0 5px rgba(66,211,146,.55)}.actions-note{margin-top:8px;color:#89919d;font:400 10px/15px Inter,sans-serif}
        @media(max-width:1050px){.actions-kanban{grid-template-columns:repeat(4,260px)}.creator-box{display:none!important}}

        </style>
    """, unsafe_allow_html=True)
    st.markdown("".join(kanban_html), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Tabela kvarova")
    show_dark_dataframe(kvarovi_f, width="stretch", height=520)
    st.markdown('</div>', unsafe_allow_html=True)

if selected_page == '📊 MTTR / MTBF':
    # Vreme rada (opening time) po alatu i ukupno, iz broja smena × 410 min.
    operating_po_alatu, operating_min_ukupno = izracunaj_operating_minute(udarci_dnevno, period, izabrani_alati)
    mtbf_min_global = (operating_min_ukupno / ukupno_kvarova) if ukupno_kvarova else 0.0
    mtbf_sati_global = mtbf_min_global / 60.0
    mttr_sati_global = mttr_ukupno / 60.0

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Globalni MTTR i MTBF (svi alati)")
    st.caption(
        "MTTR = ukupno trajanje zastoja ÷ broj kvarova. "
        "MTBF = ukupno vreme rada ÷ broj kvarova, gde je vreme rada zbir radnih dana "
        f"× broj smena × {SMENA_MINUTA} min. Dani bez upisanog broja smena vode se kao "
        f"{PODRAZUMEVANE_SMENE} smene. Vrednosti prate izabrani period i alate iz filtera."
    )
    g1, g2, g3, g4 = st.columns(4)
    with g1: kpi_card("MTTR (globalno)", f"{mttr_ukupno:,.1f} min", f"≈ {mttr_sati_global:.2f} h po kvaru")
    with g2: kpi_card("MTBF (globalno)", f"{mtbf_sati_global:,.1f} h", f"≈ {mtbf_min_global:,.0f} min po kvaru")
    with g3: kpi_card("Broj kvarova", f"{ukupno_kvarova}", "U izabranom periodu")
    with g4: kpi_card("Vreme rada", f"{operating_min_ukupno/60:,.0f} h", "Opening time (smene × 410)")
    st.markdown('</div>', unsafe_allow_html=True)

    # Target vs realno. MTTR target = 3 h (180 min), MTBF target = 6 h.
    # MTTR: zelen kada je ISPOD targeta, narandžast kada je IZNAD.
    # MTBF: zelen kada je IZNAD targeta, narandžast kada je ISPOD. Target = plav.
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Target vs realno stanje")
    st.caption("MTTR target = 3 h (180 min), MTBF target = 6 h. Zeleno = bolje od targeta, narandžasto = lošije, plavo = target.")
    T_ZELENA, T_NARANDZASTA, T_PLAVA = "#3ed598", "#f5a623", "#4fa8f5"
    MTTR_TARGET_MIN = 3 * 60
    MTBF_TARGET_SATI = 6
    tc1, tc2 = st.columns(2)
    with tc1:
        mttr_boja = T_ZELENA if mttr_ukupno <= MTTR_TARGET_MIN else T_NARANDZASTA
        fig_t_mttr = go.Figure()
        fig_t_mttr.add_bar(
            x=["Realno", "Target"], y=[mttr_ukupno, MTTR_TARGET_MIN],
            marker_color=[mttr_boja, T_PLAVA],
            text=[f"{mttr_ukupno:,.1f} min", f"{MTTR_TARGET_MIN:,.0f} min"],
            textposition="outside", textfont=dict(size=13, color="#f4f8fd"),
            hovertemplate="%{x}: %{y:.1f} min<extra></extra>",
        )
        fig_t_mttr.update_layout(title="MTTR: target vs realno (min)", yaxis=dict(title="Minuti"), showlegend=False)
        st.plotly_chart(plotly_layout(fig_t_mttr, 340), width="stretch")
    with tc2:
        mtbf_boja = T_ZELENA if mtbf_sati_global >= MTBF_TARGET_SATI else T_NARANDZASTA
        fig_t_mtbf = go.Figure()
        fig_t_mtbf.add_bar(
            x=["Realno", "Target"], y=[mtbf_sati_global, MTBF_TARGET_SATI],
            marker_color=[mtbf_boja, T_PLAVA],
            text=[f"{mtbf_sati_global:,.1f} h", f"{MTBF_TARGET_SATI:,.0f} h"],
            textposition="outside", textfont=dict(size=13, color="#f4f8fd"),
            hovertemplate="%{x}: %{y:.1f} h<extra></extra>",
        )
        fig_t_mtbf.update_layout(title="MTBF: target vs realno (h)", yaxis=dict(title="Sati"), showlegend=False)
        st.plotly_chart(plotly_layout(fig_t_mtbf, 340), width="stretch")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("MTTR po alatu")
    st.caption("Prosečno trajanje jedne intervencije po alatu (min).")
    if not kvarovi_po_alatu.empty:
        mttr = kvarovi_po_alatu.sort_values("MTTR_MIN", ascending=False)
        fig = px.bar(mttr.head(20), x="ALAT", y="MTTR_MIN", text="MTTR_MIN", title="Prosečno trajanje intervencije")
        fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
        st.plotly_chart(plotly_layout(fig, 540), width="stretch")
    else:
        st.info("Nema podataka za MTTR.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("MTBF po alatu")
    st.caption(f"Vreme rada alata ÷ broj kvarova, u satima. Vreme rada = radni dani × broj smena × {SMENA_MINUTA} min (nedostajuće smene = {PODRAZUMEVANE_SMENE}).")
    if not kvarovi_po_alatu.empty:
        mtbf_tool = kvarovi_po_alatu.copy()
        mtbf_tool["OPERATING_MIN"] = mtbf_tool["ALAT"].apply(lambda a: float(operating_po_alatu.get(compact_tool_key(a), 0.0)))
        mtbf_tool["MTBF_SATI"] = mtbf_tool.apply(lambda r: round((r["OPERATING_MIN"] / r["BROJ_KVAROVA"] / 60.0), 2) if r["BROJ_KVAROVA"] > 0 else 0.0, axis=1)
        mtbf_graf = mtbf_tool[mtbf_tool["OPERATING_MIN"] > 0].sort_values("MTBF_SATI")
        if not mtbf_graf.empty:
            fig = px.bar(mtbf_graf.head(20), x="ALAT", y="MTBF_SATI", text="MTBF_SATI", title="MTBF po alatu (sati rada između kvarova)")
            fig.update_traces(texttemplate="%{text:.1f} h", textposition="outside")
            st.plotly_chart(plotly_layout(fig, 540), width="stretch")
        else:
            st.info("Nema dovoljno podataka o vremenu rada (udarcima) za alate sa kvarovima u izabranom periodu.")
    else:
        st.info("Nema evidentiranih kvarova u izabranom periodu za MTBF.")
    st.markdown('</div>', unsafe_allow_html=True)


if selected_page == '🔧 Preventivno':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Preventivno održavanje")
    st.caption("Računa se iz taba Total punch, a alate sa 0 udaraca dopunjava iz mesečnih tabova. Pravila: 0–20% života alata na 2.500.000 udaraca, 20–80% na 2.000.000, 80–100% na 1.500.000. Životni vek alata je 150.000.000 udaraca.")

    pc1, pc2, pc3, pc4, pc5 = st.columns(5)
    with pc1: kpi_card("Za preventivu", f"{preventiva_za_broj}", "Prekoračen interval")
    with pc2: kpi_card("Blizu preventive", f"{preventiva_blizu_broj}", "Preko 80% intervala")
    with pc3: kpi_card("Početno stanje", f"{preventiva_nepostavljena_broj}", "Treba podesiti")
    with pc4: kpi_card("Alata u praćenju", f"{len(preventiva_status_f)}", "Total punch + mesečni tabovi")
    with pc5: kpi_card("Životni vek", f"{TOOL_LIFE_PUNCHES:,}", "Udaraca")

    if total_punch_lifetime.empty:
        st.error("Ne mogu da učitam listu alata. Proveri Total punch i mesečne tabove u tabeli UDARCI.")
    else:
        st.markdown("### Alati najbliži preventivi")
        fig_df = preventiva_status_f.copy()
        if not fig_df.empty:
            fig_df["OSTALO_DO_PREVENTIVE_M"] = fig_df["OSTALO_DO_PREVENTIVE"] / 1_000_000
            prikaz_fig = fig_df[fig_df["STATUS_PREVENTIVE"] != "⚪ Postavi početno stanje"].head(15)
            if not prikaz_fig.empty:
                fig = px.bar(
                    prikaz_fig,
                    x="ALAT",
                    y="OSTALO_DO_PREVENTIVE_M",
                    color="STATUS_PREVENTIVE",
                    text="STATUS_PREVENTIVE",
                    title="Koliko miliona udaraca ostaje do sledeće preventive",
                    hover_data=["LIFETIME_UDARCI", "UDARCI_OD_PREVENTIVE", "INTERVAL_PREVENTIVE", "PREKORACENJE", "ZONA_ZIVOTA"],
                    color_discrete_map=STATUS_COLOR_MAP,
                )
                st.plotly_chart(plotly_layout(fig, 470), width="stretch")
            else:
                st.info("Još nema alata sa postavljenim početnim stanjem / preventivom.")

        st.markdown("### Kartice alata")
        search_prev = st.text_input("Pretraži alat u preventivi", "", placeholder="Unesi deo naziva alata...")
        status_options = ["Svi", "🔴 Za preventivu", "🟡 Blizu preventive", "⚪ Postavi početno stanje", "🟢 OK", "⚫ Prešao životni vek"]
        status_filter = st.selectbox("Filter statusa preventive", status_options, index=0)
        cards_df = preventiva_status_f.copy()
        if search_prev:
            q = search_prev.lower().strip()
            cards_df = cards_df[cards_df["ALAT"].astype(str).str.lower().str.contains(q, na=False)]
        if status_filter != "Svi":
            cards_df = cards_df[cards_df["STATUS_PREVENTIVE"] == status_filter]
        if cards_df.empty:
            st.info("Nema alata za izabrane filtere.")
        else:
            for _, row in cards_df.head(60).iterrows():
                status = str(row.get("STATUS_PREVENTIVE", ""))
                border = "#3ed598" if "OK" in status else ("#f5b942" if "Blizu" in status else ("#f2607a" if "Za preventivu" in status else "#8a96ab"))
                card_html = f"""
                <div style='background:rgba(19,29,46,.82); border:1px solid rgba(126,170,224,0.22); border-left:3px solid {border}; border-radius:14px; padding:16px; margin-bottom:12px; box-shadow:0 6px 20px rgba(0,0,0,.28);'>
                    <div style='font-family:"Space Grotesk","Inter",sans-serif; font-size:18px; font-weight:700; color:#f4f8fd;'>{html.escape(str(row['ALAT']))}</div>
                    <div style='font-size:13px; font-weight:700; color:{border}; margin-top:3px; text-transform:uppercase; letter-spacing:.3px;'>{html.escape(status)}</div>
                    <div style='display:grid; grid-template-columns: repeat(4, minmax(160px,1fr)); gap:10px; margin-top:12px; color:#c3d0e3; font-size:13px;'>
                        <div><b style="color:#93a1b8;">Lifetime</b><br>{float(row['LIFETIME_UDARCI']):,.0f}</div>
                        <div><b style="color:#93a1b8;">Zona života</b><br>{html.escape(str(row['ZONA_ZIVOTA']))} ({float(row['PROCENAT_ZIVOTA']):.1f}%)</div>
                        <div><b style="color:#93a1b8;">Interval</b><br>{float(row['INTERVAL_PREVENTIVE']):,.0f}</div>
                        <div><b style="color:#93a1b8;">Od preventive</b><br>{float(row['UDARCI_OD_PREVENTIVE']):,.0f}</div>
                        <div><b style="color:#93a1b8;">Ostalo</b><br>{float(row['OSTALO_DO_PREVENTIVE']):,.0f}</div>
                        <div><b style="color:#93a1b8;">Prekoračenje</b><br>{float(row['PREKORACENJE']):,.0f}</div>
                        <div><b style="color:#93a1b8;">Poslednja preventiva</b><br>{html.escape(str(row['POSLEDNJA_PREVENTIVA_DATUM']))}</div>
                        <div><b style="color:#93a1b8;">Udarci tada</b><br>{float(row['POSLEDNJA_PREVENTIVA_UDARCI']):,.0f}</div>
                    </div>
                    <div style='margin-top:10px; color:#93a1b8; font-size:12.5px;'>{html.escape(str(row.get('OPIS_POSLEDNJE','')))}</div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)

        st.markdown("### Upis preventive / početnog stanja")
        form_col1, form_col2 = st.columns(2)
        alatovi_prev = sorted(preventiva_status_f["ALAT"].astype(str).unique()) if not preventiva_status_f.empty else lista_alata
        with form_col1:
            selected_tool_prev = st.selectbox("Alat", alatovi_prev, key="prev_tool")
            datum_prev = st.date_input("Datum", value=pd.Timestamp.today().date(), key="prev_date")
            tip_prev = st.radio("Šta upisuješ", ["Preventiva odrađena", "Postavi početno stanje preventive"], horizontal=False)
            current_row = preventiva_status_f[preventiva_status_f["ALAT"] == selected_tool_prev].head(1)
            current_lifetime_prev = float(current_row["LIFETIME_UDARCI"].iloc[0]) if not current_row.empty else 0

            # Za retroaktivan unos automatski vraćamo lifetime na kraj izabranog datuma:
            # trenutno stanje minus svi udarci ostvareni posle tog datuma.
            istorijski_lifetime_prev, udarci_posle_prev, obracun_pouzdan, obracun_napomena = lifetime_na_datum(
                selected_tool_prev,
                datum_prev,
                current_lifetime_prev,
                udarci_dnevno,
            )
            lifetime_widget_key = "prev_lifetime_" + re.sub(
                r"[^A-Za-z0-9_]+", "_", f"{selected_tool_prev}_{pd.to_datetime(datum_prev).date()}"
            )
            lifetime_prev = st.number_input(
                "Lifetime udarci na kraju izabranog datuma",
                min_value=0,
                value=int(round(istorijski_lifetime_prev)),
                step=1000,
                key=lifetime_widget_key,
                help="Za retroaktivan datum program od trenutnog lifetime stanja oduzima sve udarce posle izabranog datuma. Vrednost možeš ručno korigovati pre čuvanja.",
            )
            if obracun_pouzdan:
                st.caption(obracun_napomena)
            else:
                st.warning(obracun_napomena)
        with form_col2:
            opis_prev = st.text_area("Šta je urađeno / opis", value="", height=120, placeholder="Npr. čišćenje alata, kontrola prokivača, pinova, noževa, podmazivanje...")
            radio_prev = st.text_input("Ko je radio", value="")
            napomena_prev = st.text_input("Napomena", value="")
            potvrdi_prev = st.checkbox("Potvrđujem upis preventive u Google Sheets")
        if st.button("Sačuvaj preventivu / početno stanje", width="stretch", disabled=not potvrdi_prev):
            if not selected_tool_prev:
                st.error("Izaberi alat.")
            else:
                interval_prev, zona_prev, pct_prev = preventive_interval_for_lifetime(lifetime_prev)
                last_life_prev = 0
                if not current_row.empty:
                    last_life_prev = float(current_row["POSLEDNJA_PREVENTIVA_UDARCI"].iloc[0] or 0)
                punches_since_prev = max(float(lifetime_prev) - float(last_life_prev), 0)
                payload = {"action": "recordPreventive", "spreadsheetId": SHEET_ID_UDARCI, "toolName": selected_tool_prev, "date": str(pd.to_datetime(datum_prev).date()), "recordType": "POCETNO_STANJE" if tip_prev.startswith("Postavi") else "PREVENTIVA", "lifetimePunches": float(lifetime_prev), "punchesSincePrevious": 0 if tip_prev.startswith("Postavi") else float(punches_since_prev), "interval": int(interval_prev), "lifeZone": zona_prev, "description": opis_prev, "person": radio_prev, "note": napomena_prev}
                res = pozovi_apps_script(payload)
                st.session_state["preventive_write_result"] = res
                if res.get("ok"):
                    st.success(res.get("message", "Upisano."))
                    st.cache_data.clear()
                    st.info("Keš je očišćen. Osveži stranicu da vidiš novo odbrojavanje.")
                else:
                    st.error(res.get("message", "Upis preventive nije uspeo."))
        prev_rez = st.session_state.get("preventive_write_result")
        if prev_rez:
            with st.expander("Detalji poslednjeg upisa preventive"):
                st.json(prev_rez)
        with st.expander("Istorija preventive"):
            show_dark_dataframe(preventiva_istorija.sort_values("DATUM", ascending=False) if not preventiva_istorija.empty else preventiva_istorija, width="stretch", height=420)
        with st.expander("Tabela statusa preventive"):
            show_dark_dataframe(preventiva_status_f, width="stretch", height=520)
    st.markdown('</div>', unsafe_allow_html=True)


if selected_page == '🔮 Prediktivno':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Prediktivno održavanje")
    st.caption(
        f"Traži delove koji se troše u pravilnom ritmu: kada se isti tip kvara na alatu ponovi "
        f"{PREDIKTIVNI_MIN_PONAVLJANJA} ili više puta, i to u proseku na manje od "
        f"{PREDIKTIVNI_PRAG_UDARACA:,} udaraca, program izračuna prosečan razmak (u udarcima) "
        f"između pojavljivanja i predviđa kada se očekuje sledeći kvar. Broj udaraca po datumu se "
        f"rekonstruiše iz mesečnih tabova."
    )

    prediktivno = build_prediktivno(kvarovi, udarci_dnevno)

    ocekivan_sada = int((prediktivno["STATUS"] == "🔴 Očekivan kvar").sum()) if not prediktivno.empty else 0
    blizu_sada = int((prediktivno["STATUS"] == "🟡 Blizu").sum()) if not prediktivno.empty else 0

    kp1, kp2, kp3, kp4 = st.columns(4)
    with kp1: kpi_card("Prepoznatih obrazaca", f"{len(prediktivno)}", "Kvar × alat")
    with kp2: kpi_card("Očekivano sada", f"{ocekivan_sada}", "Prešao prosečan razmak")
    with kp3: kpi_card("Blizu", f"{blizu_sada}", "≤ 20% do očekivanog")
    with kp4: kpi_card("Prag učestalosti", f"{PREDIKTIVNI_PRAG_UDARACA:,}", f"Min {PREDIKTIVNI_MIN_PONAVLJANJA} ponavljanja")

    if prediktivno.empty:
        st.info(
            "Još nema kvara koji se ponovio dovoljno puta u dovoljno kratkom razmaku da bi se pravio obrazac. "
            "Čim se neki kvar javi 3+ puta na manje od 2.500.000 udaraca u proseku, pojaviće se ovde."
        )
    else:
        boja = {"🔴 Očekivan kvar": "#f2607a", "🟡 Blizu": "#f5b942", "🟢 Prati": "#3ed598"}
        kartice = []
        for _, r in prediktivno.iterrows():
            akcenat = boja.get(r["STATUS"], "#4fa8f5")
            primer = html.escape(str(r["PRIMER_OPISA"])) if r["PRIMER_OPISA"] else ""
            primer_html = f'<div style="margin-top:8px;color:#9ca7b5;font:400 11px/16px Inter,sans-serif">„{primer}"</div>' if primer else ""
            kartice.append(
                f'<div style="margin-bottom:10px;padding:13px 15px;background:#141a22;'
                f'border:1px solid #333b46;border-left:4px solid {akcenat};border-radius:5px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px">'
                f'<b style="color:#e8ecf3;font:600 14px Inter,sans-serif">{html.escape(str(r["ALAT"]))}</b>'
                f'<span style="color:{akcenat};font:700 11px \'JetBrains Mono\',monospace">{html.escape(str(r["STATUS"]))}</span>'
                f'</div>'
                f'<div style="margin-top:5px;color:#c3d0e3;font:600 12px Inter,sans-serif">Kvar: {html.escape(str(r["KVAR"]))}'
                f' <span style="color:#89919d;font-weight:400">· ponovljen {int(r["BROJ_PONAVLJANJA"])}×</span></div>'
                f'<div style="margin-top:7px;color:#dfe6f0;font:500 13px \'JetBrains Mono\',monospace">'
                f'⌀ na svakih <b style="color:{akcenat}">{int(r["PROSECAN_INTERVAL"]):,}</b> udaraca</div>'
                f'<div style="margin-top:5px;color:#9ca7b5;font:400 11px \'JetBrains Mono\',monospace">'
                f'Od poslednjeg ({html.escape(str(r["POSLEDNJI_DATUM"]))}): {int(r["UDARCI_OD_POSLEDNJEG"]):,} · '
                f'do očekivanog: {int(r["OSTALO_DO_OCEKIVANOG"]):,}</div>'
                f'{primer_html}'
                f'</div>'
            )
        st.markdown("".join(kartice), unsafe_allow_html=True)

        prikaz = prediktivno.rename(columns={
            "ALAT": "Alat", "KVAR": "Kvar", "BROJ_PONAVLJANJA": "Ponavljanja",
            "PROSECAN_INTERVAL": "Prosečan interval (udaraca)", "POSLEDNJI_DATUM": "Poslednji put",
            "UDARCI_OD_POSLEDNJEG": "Od poslednjeg", "OSTALO_DO_OCEKIVANOG": "Do očekivanog",
            "STATUS": "Status", "PRIMER_OPISA": "Primer opisa",
        })
        with st.expander("Tabela prediktivnih obrazaca"):
            show_dark_dataframe(prikaz, width="stretch", height=420)
    st.markdown('</div>', unsafe_allow_html=True)


if selected_page == '🚨 Kritični alati':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Kritični alati - mapa rizika")
    st.caption("Veličina kruga pokazuje ukupno trajanje zastoja. Naziv alata je prikazan pored kruga, a detalji se vide kada pređeš kursorom.")
    if not analitika.empty:
        plot_df = analitika.copy()
        fig = px.scatter(
            plot_df,
            x="UDARCI",
            y="BROJ_KVAROVA",
            size="ZASTOJ_MIN",
            color="STATUS",
            text="ALAT",
            hover_name="ALAT",
            hover_data={
                "UDARCI": ":,.0f",
                "BROJ_KVAROVA": True,
                "ZASTOJ_MIN": ":.0f",
                "MTTR_MIN": ":.1f",
                "KVAROVA_NA_1M_UDARACA": ":.2f",
                "STATUS": True,
                "ALAT": False,
            },
            title="Mapa rizika: udarci / broj kvarova / trajanje zastoja",
            size_max=72,
            color_discrete_map=STATUS_COLOR_MAP,
        )
        fig.update_traces(
            textposition="top center",
            marker=dict(line=dict(width=1.5, color="rgba(255,255,255,0.55)")),
            textfont=dict(size=13, color="#f4f8fd"),
        )
        fig.update_layout(uniformtext_minsize=10, uniformtext_mode="show")
        st.plotly_chart(plotly_layout(fig, 610), width="stretch")
        st.markdown("#### Detaljna tabela")
        show_dark_dataframe(analitika, width="stretch", height=380)
    else:
        st.info("Nema dovoljno podataka za analitiku alata.")
    st.markdown('</div>', unsafe_allow_html=True)

    # ---- Top 3 kvara za izabrani period (primarno broj ponavljanja, sekundarno zastoj) ----
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Top 3 kvara u izabranom periodu")
    st.caption("Rangirano prvo po broju ponavljanja, a kod istog broja po ukupnom trajanju zastoja. Levi stubić je broj ponavljanja, desni ukupan zastoj u minutima.")
    if not kvarovi_f.empty and "KATEGORIJA" in kvarovi_f.columns:
        top3 = kvarovi_f.groupby("KATEGORIJA", as_index=False).agg(
            BROJ=("KATEGORIJA", "count"),
            ZASTOJ_MIN=("TRAJANJE", "sum") if "TRAJANJE" in kvarovi_f.columns else ("KATEGORIJA", "count"),
        )
        if "TRAJANJE" not in kvarovi_f.columns:
            top3["ZASTOJ_MIN"] = 0.0
        top3 = top3.sort_values(["BROJ", "ZASTOJ_MIN"], ascending=[False, False]).head(3)

        if top3.empty:
            st.info("Nema kvarova u izabranom periodu.")
        else:
            fig_top = go.Figure()
            fig_top.add_bar(
                x=top3["KATEGORIJA"], y=top3["BROJ"], name="Broj ponavljanja",
                marker_color="#f2607a", text=[f"{int(v)}×" for v in top3["BROJ"]],
                textposition="outside", textfont=dict(size=13, color="#f4f8fd"),
                hovertemplate="<b>%{x}</b><br>Ponavljanja: %{y}<extra></extra>",
            )
            fig_top.add_bar(
                x=top3["KATEGORIJA"], y=top3["ZASTOJ_MIN"], name="Zastoj (min)",
                marker_color="#4fa8f5", yaxis="y2",
                text=[f"{float(v):.0f} min" for v in top3["ZASTOJ_MIN"]],
                textposition="outside", textfont=dict(size=13, color="#f4f8fd"),
                hovertemplate="<b>%{x}</b><br>Zastoj: %{y:.0f} min<extra></extra>",
            )
            fig_top.update_layout(
                barmode="group",
                title="Najčešći kvarovi: ponavljanja i ukupan zastoj",
                yaxis=dict(title="Broj ponavljanja"),
                yaxis2=dict(title="Zastoj (min)", overlaying="y", side="right",
                            gridcolor="rgba(0,0,0,0)", color="#bfc7d4"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(plotly_layout(fig_top, 470), width="stretch")

            prikaz_top3 = top3.rename(columns={
                "KATEGORIJA": "Kvar", "BROJ": "Ponavljanja", "ZASTOJ_MIN": "Ukupan zastoj (min)",
            })
            show_dark_dataframe(prikaz_top3, width="stretch", height=160)
    else:
        st.info("Nema kvarova u izabranom periodu.")
    st.markdown('</div>', unsafe_allow_html=True)

if selected_page == '📦 Rezervni delovi':
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi_card("Redova u bazi", f"{len(delovi)}", "Svaka lokacija posebno")
    with c2: kpi_card("Grupisanih delova", f"{len(grupisani_delovi)}", "Po ID dela ili nazivu")
    with c3: kpi_card("Stanje 0", f"{len(delovi_zero)}", "Lokacije bez komada")
    with c4: kpi_card("Ispod minimuma", f"{len(delovi_min)}", "Po grupisanom stanju")
    with c5: kpi_card("Preko maksimuma", f"{len(delovi_max)}", "Ako postoji max stanje")

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Kartice delova sa slikom")
    st.caption("Radi kada u BAZA A dodaš kolonu Image_URL / Slika sa direktnim linkom do fotografije. Prikazani su svi delovi jedan ispod drugog; skroluj za ostale.")
    sve_kartice_delova = grupisani_delovi.copy()
    # Poređaj kartice po redosledu unosa u BAZA_A (prvi put kada se deo pojavi u tabeli),
    # umesto po stanju/nazivu. Grupisani delovi se ovde samo lokalno presortiraju.
    if not sve_kartice_delova.empty and "KLJUC_DELA" in sve_kartice_delova.columns and not delovi.empty and "KLJUC_DELA" in delovi.columns:
        red_unosa = {k: i for i, k in enumerate(delovi.drop_duplicates(subset="KLJUC_DELA")["KLJUC_DELA"].tolist())}
        sve_kartice_delova = (
            sve_kartice_delova
            .assign(_RED=sve_kartice_delova["KLJUC_DELA"].map(red_unosa))
            .sort_values("_RED", na_position="last")
            .drop(columns="_RED")
        )
    if not sve_kartice_delova.empty:
        with st.container(height=470):
            for _, row in sve_kartice_delova.iterrows():
                c_img, c_txt = st.columns([0.2, 0.8])
                with c_img:
                    img_url = direktan_link_slike(row.get("IMAGE_URL", ""))
                    if img_url.startswith("http"):
                        st.image(img_url, width="stretch")
                    else:
                        st.markdown("🧩")
                with c_txt:
                    st.markdown(f"**{row.get('NAZIV','')}**")
                    st.caption(f"Stanje: {row.get('UKUPNO_STANJE',0)} | Min: {row.get('MINIMUM',0)} | Max: {row.get('MAKSIMUM',0)}")
                    st.caption(f"Lokacija: {row.get('LOKACIJE','')} | Status: {row.get('STATUS','')}")
                st.markdown("<hr style='margin:4px 0;border:none;border-top:1px solid rgba(255,255,255,0.08)'>", unsafe_allow_html=True)
    else:
        st.info("Nema delova za prikaz.")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Pretraga rezervnih delova")
    query = st.text_input("Pretraži po nazivu, lokaciji, projektu/modelu, ID dela ili statusu zalihe", "")
    prikaz = grupisani_delovi.copy()
    if query and not prikaz.empty:
        # Pretraga bez obzira na kvačice (ležaj = lezaj) i bez regex-a (znaci kao
        # "(", ".", "+" se traže doslovno, a ne kao specijalni znaci).
        def _norm_pretraga(vrednost):
            return strip_accents(str(vrednost)).replace("đ", "dj")
        q = _norm_pretraga(query)
        mask = prikaz.apply(lambda row: q in _norm_pretraga(" ".join(str(v) for v in row.values)), axis=1)
        prikaz = prikaz[mask]
    show_dark_dataframe(prikaz, width="stretch", height=460)
    with st.expander("Provera učitavanja BAZA A"):
        try:
            raw_delovi = ucitaj_delove_raw_sheet()
            st.write("Prepoznate kolone iz Google Sheets taba BAZA A:")
            st.write(list(raw_delovi.columns))
            st.write("Prvih 10 redova posle prepoznavanja headera:")
            show_dark_dataframe(raw_delovi.head(10), width="stretch", height=300)
            st.write("Standardizovane kolone koje program koristi:")
            st.write(list(delovi.columns) if not delovi.empty else "Nema standardizovanih redova")
        except Exception as e:
            st.warning(f"Ne mogu da prikažem proveru učitavanja: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Alarmi za nabavku")
    if not grupisani_delovi.empty:
        alarms = grupisani_delovi[grupisani_delovi["STATUS"].isin(["🔴 Nema", "🟡 Ispod minimuma"])].head(30)
        if alarms.empty:
            st.success("Nema delova u alarmu po trenutnim pravilima.")
        else:
            kolone_alarm = ["PART_ID", "NAZIV", "UKUPNO_STANJE", "MINIMUM", "MAKSIMUM", "BROJ_LOKACIJA", "LOKACIJE", "STATUS", "STATUS_IZ_TABELE"]
            kolone_alarm = [c for c in kolone_alarm if c in alarms.columns]
            show_dark_dataframe(alarms[kolone_alarm], width="stretch", height=430)
    else:
        st.info("Tabela rezervnih delova nije učitana ili je prazna.")
    st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("Detaljan prikaz - svaka lokacija posebno"):
        show_dark_dataframe(delovi, width="stretch", height=500)

if selected_page == '🗂️ Akcije':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Akcije")

    # Privremeno dodate akcije iz trenutne sesije - ne upisuju se u Google Sheets.
    lokalne_akcije = st.session_state.get("lokalne_akcije", [])
    akcije_prikaz = akcije.copy() if akcije is not None else pd.DataFrame()
    if lokalne_akcije:
        akcije_prikaz = pd.concat([akcije_prikaz, pd.DataFrame(lokalne_akcije)], ignore_index=True)

    c_view, c_search, c_add = st.columns([1.1, 2.4, 1.1])
    with c_view:
        prikaz_akcija = st.radio("Prikaz akcija", ["Kanban", "Lista"], horizontal=True, label_visibility="collapsed")
    with c_search:
        pretraga_akcija = st.text_input("Pretraži akcije", "", placeholder="Pretraži po opisu, alatu, statusu, odgovornom...", label_visibility="collapsed")
    with c_add:
        dodaj_akciju = st.checkbox("Dodaj akciju", value=False)

    if dodaj_akciju:
        with st.form("forma_dodaj_akciju", clear_on_submit=True):
            fc1, fc2, fc3 = st.columns([2, 1, 1])
            with fc1:
                novi_naslov = st.text_input("Naziv / akcija")
                novi_opis = st.text_area("Opis", height=90)
            with fc2:
                novi_status = st.selectbox("Status", ["Backlog", "Za uraditi", "U toku", "Čeka deo", "Čeka Kinu", "Testiranje", "Završeno"])
                novi_prioritet = st.selectbox("Prioritet", ["VISOK", "SREDNJI", "NIZAK"])
            with fc3:
                novi_alat = st.text_input("Alat / projekat")
                novi_rok = st.date_input("Rok", value=pd.Timestamp.today().date())
                novi_odgovoran = st.text_input("Odgovoran")
            sacuvaj_lokalno = st.form_submit_button("Dodaj u prikaz")
            if sacuvaj_lokalno and novi_naslov.strip():
                item = {
                    "ID": f"LOCAL-{len(lokalne_akcije)+1:03d}",
                    "NASLOV": novi_naslov.strip(),
                    "OPIS": novi_opis.strip(),
                    "STATUS": novi_status,
                    "PRIORITET": novi_prioritet,
                    "ALAT": novi_alat.strip(),
                    "ROK": pd.to_datetime(novi_rok).strftime("%d.%m.%Y"),
                    "ODGOVORAN": novi_odgovoran.strip(),
                    "IZVOR": "Privremeno u ovoj sesiji",
                }
                st.session_state.setdefault("lokalne_akcije", []).append(item)
                st.success("Akcija je dodata u trenutni prikaz. Za trajni upis dodaj je i u Google Sheets tab AKCIJE.")
                st.rerun()

    if akcije_prikaz.empty:
        st.warning("Nisam našao tab AKCIJE / AKCIONI PLAN u povezanim Google Sheets fajlovima. Kada taj tab postoji, ovde će se prikazati stvarne kartice.")
    else:
        for c in ["ID", "NASLOV", "OPIS", "STATUS", "PRIORITET", "ALAT", "ROK", "ODGOVORAN", "IZVOR"]:
            if c not in akcije_prikaz.columns:
                akcije_prikaz[c] = ""
        if pretraga_akcija:
            q = strip_accents(pretraga_akcija)
            mask = akcije_prikaz[["ID", "NASLOV", "OPIS", "STATUS", "PRIORITET", "ALAT", "ROK", "ODGOVORAN"]].fillna("").apply(
                lambda r: q in strip_accents(" ".join(str(x) for x in r)), axis=1
            )
            akcije_prikaz = akcije_prikaz[mask].copy()

        st.caption(f"Prikazano akcija: {len(akcije_prikaz)}")

        if prikaz_akcija == "Lista":
            show_dark_dataframe(akcije_prikaz[["ID", "NASLOV", "STATUS", "PRIORITET", "ALAT", "ROK", "ODGOVORAN", "OPIS", "IZVOR"]], width="stretch", height=620)
        else:
            preferred_order = ["Backlog", "Za uraditi", "U toku", "Čeka deo", "Čeka Kinu", "Testiranje", "Završeno"]
            all_statuses = [x for x in preferred_order if x in set(akcije_prikaz["STATUS"].astype(str))]
            all_statuses += [x for x in akcije_prikaz["STATUS"].astype(str).dropna().unique().tolist() if x not in all_statuses]
            if not all_statuses:
                all_statuses = ["Za uraditi"]
            column_accents = {
                "Backlog":"#89919d", "Za uraditi":"#ffb77b", "U toku":"#9ecaff", "Čeka deo":"#f5b942",
                "Čeka Kinu":"#c8c6c5", "Testiranje":"#db7900", "Završeno":"#42d392"
            }
            kanban_cols = []
            for status_name in all_statuses:
                items = akcije_prikaz[akcije_prikaz["STATUS"].astype(str) == status_name]
                cards = []
                for _, item in items.iterrows():
                    pr = normalizuj_prioritet_akcije(item.get("PRIORITET", ""))
                    priority_class = "priority-high" if pr == "VISOK" else ("priority-low" if pr == "NIZAK" else "priority-medium")
                    title = html.escape(str(item.get("NASLOV", ""))[:180])
                    opis = html.escape(str(item.get("OPIS", ""))[:260])
                    alat = html.escape(str(item.get("ALAT", ""))[:80])
                    rok = html.escape(str(item.get("ROK", ""))[:40])
                    odgovoran = html.escape(str(item.get("ODGOVORAN", ""))[:60])
                    aid = html.escape(str(item.get("ID", ""))[:28])
                    footer_left = f"🔧 {alat}" if alat else (f"👤 {odgovoran}" if odgovoran else "")
                    footer_right = f"▣ {rok}" if rok else ""
                    cards.append(
                        '<div class="action-card">'
                        f'<div class="action-card-top"><span class="priority-chip {priority_class}">{pr}</span><span class="action-id">#{aid}</span></div>'
                        f'<div class="action-title">{title}</div>'
                        f'<div class="action-comment">{opis}</div>'
                        f'<div class="action-card-footer"><span>{footer_left}</span><span>{footer_right}</span></div>'
                        '</div>'
                    )
                if not cards:
                    cards.append('<div class="kanban-empty">Nema akcija u ovoj koloni</div>')
                accent = column_accents.get(status_name, "#89919d")
                kanban_cols.append(
                    f'<section class="action-column" style="--column-accent:{accent}">'
                    f'<header class="action-column-header"><span>{html.escape(status_name.upper())}</span><b>{len(items):02d}</b></header>'
                    f'<div class="action-column-body">{"".join(cards)}</div></section>'
                )
            st.markdown('<div class="actions-kanban">' + ''.join(kanban_cols) + '</div>', unsafe_allow_html=True)
            st.markdown('<div class="system-status-footer"><span><i></i> SISTEM AKTIVAN</span><span>AKCIJE SE ČITAJU IZ GOOGLE SHEETS TABA AKCIJE / AKCIONI PLAN</span></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

if selected_page == '📝 Unos udaraca':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Unos udaraca u Google Sheets")
    st.caption("Unos je napravljen za više unosa dnevno. Ako ćelija već ima vrednost, program prikazuje postojeću vrednost i pita da li želiš da sabereš ili zameniš.")

    with st.expander("Podešavanje veze za upis", expanded=not bool(get_apps_script_url())):
        st.write("Veza za upis u Google Sheets već je podešena u `config.json` fajlu.")

        current_url = get_apps_script_url()
        url_input = st.text_input(
            "Apps Script Web App URL",
            value=current_url,
            placeholder="https://script.google.com/macros/s/.../exec",
            type="password",
            help="URL je već uključen u paket. Ovo polje koristi samo ako kasnije želiš da promeniš vezu."
        )

        col_url1, col_url2 = st.columns([1, 1])
        with col_url1:
            if st.button("💾 Sačuvaj Apps Script link", width="stretch"):
                url_to_save = str(url_input).strip()
                if url_to_save.startswith("https://script.google.com/"):
                    try:
                        save_local_config({"apps_script_url": url_to_save})
                        st.session_state["apps_script_url_runtime"] = url_to_save
                        st.success("Apps Script link je sačuvan u config.json.")
                    except Exception as e:
                        st.session_state["apps_script_url_runtime"] = url_to_save
                        st.warning(f"URL važi za ovu sesiju, ali lokalni fajl nije mogao da se sačuva: {e}")
                elif url_to_save:
                    st.error("Link ne izgleda kao Google Apps Script Web App URL. Treba da počinje sa https://script.google.com/")
                else:
                    st.error("Prvo nalepi Apps Script Web App URL.")

        with col_url2:
            if st.button("🧹 Obriši sačuvani link", width="stretch"):
                try:
                    save_local_config({"apps_script_url": ""})
                    st.session_state["apps_script_url_runtime"] = ""
                    st.warning("Lokalno sačuvani Apps Script link je obrisan.")
                except Exception as e:
                    st.session_state["apps_script_url_runtime"] = ""
                    st.warning(f"URL je uklonjen iz ove sesije, ali lokalni fajl nije mogao da se izmeni: {e}")

        if url_input:
            st.session_state["apps_script_url_runtime"] = str(url_input).strip()

        if get_apps_script_url():
            st.success("URL je podešen i spreman za upis.")
        else:
            st.warning("URL još nije podešen. Možeš popuniti formu, ali upis neće raditi dok se ne doda Apps Script URL.")

    st.markdown("### Forma za unos")
    col_a, col_b, col_c = st.columns([0.8, 0.8, 1.4])
    danas = pd.Timestamp.today().date()
    with col_a:
        datum_unosa = st.date_input("Datum udaraca", value=danas)
    with col_b:
        mesec_auto = mesec_iz_datuma(datum_unosa)
        mesec_unosa = st.text_input("Mesečni tab", value=mesec_auto, help="Program samo obaveštava ako ovaj tab ne postoji. Ne pravi novi mesečni tab automatski.")
    with col_c:
        alati_za_unos = sorted([x for x in lista_alata if str(x).strip()]) if 'lista_alata' in globals() else []
        alat_unosa = st.selectbox("Alat", alati_za_unos, index=0 if alati_za_unos else None, placeholder="Izaberi alat")

    col_d, col_e, col_f = st.columns([0.8, 1.0, 1.2])
    with col_d:
        broj_udaraca_unos = st.number_input("Broj udaraca za unos", min_value=0, step=1, value=0)
    with col_e:
        nacin_upisa = st.radio("Način upisa", ["Saberi sa postojećim", "Zameni postojeću vrednost"], horizontal=False)
    with col_f:
        napomena_unos = st.text_input("Napomena", value="", placeholder="Opcionalno, npr. smena / razlog korekcije")

    col_g, col_h = st.columns([0.8, 2.0])
    with col_g:
        postojece_smene = load_smene().get(smena_kljuc(datum_unosa, alat_unosa) if alat_unosa else "", PODRAZUMEVANE_SMENE)
        broj_smena_unos = st.number_input(
            "Broj smena", min_value=0, max_value=3, step=1, value=int(postojece_smene),
            help=f"Koliko smena je alat radio tog dana. Jedna smena = {SMENA_MINUTA} min. Koristi se za MTBF (vreme rada)."
        )
    with col_h:
        st.caption(f"Vreme rada za taj dan = {broj_smena_unos} × {SMENA_MINUTA} = {int(broj_smena_unos) * SMENA_MINUTA} min. Broj smena se čuva lokalno (smene.json) po danu i alatu; dani bez upisa vode se kao {PODRAZUMEVANE_SMENE} smene.")

    payload_base = {
        "spreadsheetId": SHEET_ID_UDARCI,
        "monthSheet": mesec_unosa,
        "date": str(datum_unosa),
        "day": int(pd.to_datetime(datum_unosa).day),
        "toolName": str(alat_unosa) if alat_unosa else "",
    }

    check_col, save_col = st.columns([0.55, 0.45])
    with check_col:
        if st.button("Proveri ćeliju u Google Sheets", width="stretch"):
            data = pozovi_apps_script({"action": "checkPunchCell", **payload_base})
            st.session_state["punch_check_result"] = data

    rezultat_provere = st.session_state.get("punch_check_result")
    if rezultat_provere:
        if rezultat_provere.get("ok"):
            st.success("Ćelija je pronađena.")
            pc1, pc2, pc3, pc4 = st.columns(4)
            with pc1: kpi_card("Tab", str(rezultat_provere.get("sheet", "")), "Mesečni sheet")
            with pc2: kpi_card("Ćelija", str(rezultat_provere.get("a1", "")), "Mesto upisa")
            with pc3: kpi_card("Postojeće", str(rezultat_provere.get("existingValue", "")), "Trenutna vrednost")
            nova_vrednost_preview = rezultat_provere.get("newValueIfAdd", "") if nacin_upisa == "Saberi sa postojećim" else broj_udaraca_unos
            with pc4: kpi_card("Posle upisa", str(nova_vrednost_preview), nacin_upisa)
        else:
            st.error(rezultat_provere.get("message", "Provera nije uspela."))

    with save_col:
        potvrda = st.checkbox("Potvrđujem upis u Google Sheets")
        if st.button("Sačuvaj udarce", width="stretch", disabled=not potvrda):
            mode = "add" if nacin_upisa == "Saberi sa postojećim" else "replace"
            payload = {
                "action": "writePunchCell",
                **payload_base,
                "value": int(broj_udaraca_unos),
                "mode": mode,
                "note": napomena_unos,
            }
            data = pozovi_apps_script(payload)
            st.session_state["punch_write_result"] = data
            if data.get("ok"):
                # Zabeleži broj smena za taj dan i alat (za MTBF / vreme rada).
                if alat_unosa:
                    save_smena(datum_unosa, alat_unosa, broj_smena_unos)
                st.success(data.get("message", "Upisano."))
                st.cache_data.clear()
                st.info("Keš je očišćen. Osveži stranicu ili sačekaj sledeće automatsko osvežavanje da se grafici učitaju sa novim podatkom.")
            else:
                st.error(data.get("message", "Upis nije uspeo."))

    # Broj smena se može sačuvati i bez upisa udaraca (npr. ako su udarci već upisani ranije).
    if st.button("Sačuvaj samo broj smena za ovaj dan/alat", width="stretch"):
        if alat_unosa:
            if save_smena(datum_unosa, alat_unosa, broj_smena_unos):
                st.success(f"Sačuvano: {alat_unosa}, {datum_unosa} → {int(broj_smena_unos)} smene ({int(broj_smena_unos) * SMENA_MINUTA} min rada).")
            else:
                st.error("Nisam uspeo da sačuvam broj smena.")
        else:
            st.warning("Prvo izaberi alat.")

    upis_rez = st.session_state.get("punch_write_result")
    if upis_rez:
        with st.expander("Detalji poslednjeg upisa"):
            st.json(upis_rez)

    st.markdown("### Važna pravila")
    st.markdown("""
    - Ako mesečni tab ne postoji, program će samo javiti grešku. Ne pravi novi mesec automatski.
    - Ako ćelija već ima vrednost, izaberi **Saberi sa postojećim** za više unosa u toku dana.
    - Program ne menja formule u tabovima **Total punch**, **Preventivno** i **Mold lifetime**.
    - Preventivno održavanje u programu računa se iz učitanih podataka, bez automatskog prepravljanja formula u Google Sheets-u.
    """)
    st.markdown('</div>', unsafe_allow_html=True)



if selected_page == '📈 Udarci po periodu':
    st.markdown("""
        <div class="module-command-bar">
            <div class="command-tabs"><span class="command-tab active">▣ Pregled udaraca</span></div>
            <div class="command-search">Dnevni podaci iz mesečnih tabova UDARCI</div>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("### Udarci po izabranom periodu")
    st.caption("Kalendar i izbor perioda na ovoj stranici ne utiču na ostale module programa.")

    if udarci_dnevno.empty or not udarci_dnevno["DATUM"].notna().any():
        st.warning("Nema dostupnih dnevnih podataka o udarcima za prikaz.")
    else:
        lokalni_min = udarci_dnevno["DATUM"].min().date()
        lokalni_max = udarci_dnevno["DATUM"].max().date()

        period_col, summary_col = st.columns([1.05, 2.95], vertical_alignment="bottom")
        with period_col:
            lokalni_period = st.date_input(
                "Izaberi period",
                value=(lokalni_min, lokalni_max),
                min_value=lokalni_min,
                max_value=lokalni_max,
                key="udarci_period_local_calendar",
                help="Klikni početni i krajnji datum u kalendaru. Ovaj filter važi samo za ovaj modul.",
            )

        if isinstance(lokalni_period, tuple) and len(lokalni_period) == 2:
            lokalni_od = pd.to_datetime(lokalni_period[0])
            lokalni_do = pd.to_datetime(lokalni_period[1]) + pd.Timedelta(days=1)
        else:
            lokalni_od = pd.to_datetime(lokalni_min)
            lokalni_do = pd.to_datetime(lokalni_max) + pd.Timedelta(days=1)

        dnevno_period = udarci_dnevno[
            (udarci_dnevno["DATUM"] >= lokalni_od) &
            (udarci_dnevno["DATUM"] < lokalni_do)
        ].copy()

        period_kraj = lokalni_do - pd.Timedelta(days=1)
        broj_dana = max((lokalni_do - lokalni_od).days, 1)
        aktivni_alati = dnevno_period.loc[dnevno_period["UDARCI"] > 0, "ALAT"].nunique()
        with summary_col:
            summary_html = (
                '<div class="filter-summary-bar">'
                f'<span class="filter-summary-item">Period: <b>{lokalni_od.strftime("%d.%m.%Y")} - {period_kraj.strftime("%d.%m.%Y")}</b></span>'
                f'<span class="filter-summary-item">Dani: <b>{broj_dana}</b></span>'
                f'<span class="filter-summary-item">Alati sa udarcima: <b>{aktivni_alati}</b></span>'
                '</div>'
            )
            st.markdown(summary_html, unsafe_allow_html=True)

        po_alatu_period = (
            dnevno_period.groupby("ALAT", as_index=False)["UDARCI"]
            .sum()
            .sort_values("UDARCI", ascending=False)
        )
        po_alatu_period = po_alatu_period[po_alatu_period["UDARCI"] > 0]

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Broj udaraca po alatu")
        if po_alatu_period.empty:
            st.info("U izabranom periodu nema evidentiranih udaraca.")
        else:
            fig_alati_period = px.bar(
                po_alatu_period.sort_values("UDARCI", ascending=True),
                x="UDARCI",
                y="ALAT",
                orientation="h",
                text="UDARCI",
                labels={"UDARCI": "Broj udaraca", "ALAT": "Alat"},
            )
            fig_alati_period.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                hovertemplate="<b>%{y}</b><br>Udarci: %{x:,.0f}<extra></extra>",
            )
            fig_alati_period.update_layout(
                yaxis={"categoryorder": "total ascending"},
                margin=dict(t=20, l=10, r=70, b=20),
            )
            plotly_layout(fig_alati_period, height=max(430, 34 * len(po_alatu_period) + 120))
            st.plotly_chart(fig_alati_period, width="stretch", config={"displaylogo": False})
        st.markdown('</div>', unsafe_allow_html=True)

        ukupan_period = int(dnevno_period["UDARCI"].sum()) if not dnevno_period.empty else 0
        total_left, total_center, total_right = st.columns([1, 1.4, 1])
        with total_center:
            kpi_card(
                "Ukupan broj udaraca za sve alate",
                f"{ukupan_period:,}",
                f"Period {lokalni_od.strftime('%d.%m.%Y')} - {period_kraj.strftime('%d.%m.%Y')}",
            )

        po_projektu_period = (
            dnevno_period.groupby("PROJEKAT", as_index=False)["UDARCI"]
            .sum()
            .sort_values("UDARCI", ascending=False)
        )
        po_projektu_period = po_projektu_period[po_projektu_period["UDARCI"] > 0]

        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Broj udaraca po projektu")
        if po_projektu_period.empty:
            st.info("U izabranom periodu nema podataka za prikaz po projektu.")
        else:
            fig_projekti_period = px.bar(
                po_projektu_period,
                x="PROJEKAT",
                y="UDARCI",
                text="UDARCI",
                labels={"PROJEKAT": "Projekat", "UDARCI": "Broj udaraca"},
            )
            fig_projekti_period.update_traces(
                texttemplate="%{text:,.0f}",
                textposition="outside",
                hovertemplate="<b>%{x}</b><br>Udarci: %{y:,.0f}<extra></extra>",
            )
            fig_projekti_period.update_layout(margin=dict(t=30, l=10, r=10, b=20))
            plotly_layout(fig_projekti_period, height=420)
            st.plotly_chart(fig_projekti_period, width="stretch", config={"displaylogo": False})
        st.markdown('</div>', unsafe_allow_html=True)


if selected_page == '📚 Dokumentacija':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Dokumentacija / Procedure")
    st.caption("Učitava tab DOKUMENTACIJA iz Google Sheets tabele rezervnih delova. Word dokumenti se otvaraju preko Google Drive linka.")

    if dokumentacija.empty:
        st.warning("Nema učitane dokumentacije. Proveri da li tab ima naziv DOKUMENTACIJA i da li ima bar kolone Naziv dokumenta i Link.")
        primer_docs = pd.DataFrame([
            {"Naziv dokumenta": "Podešavanje APP350 alata", "Kategorija": "Procedura", "Tip": "Word", "Link": "https://drive.google.com/...", "Opis": "Uputstvo za podešavanje", "Mašina/Alat": "APP350", "Jezik": "Srpski", "Aktivno": "DA"},
        ])
        st.write("Primer kako tab može da izgleda:")
        show_dark_dataframe(primer_docs, width="stretch")
    else:
        d1, d2, d3, d4 = st.columns(4)
        with d1: kpi_card("Dokumenata", f"{len(dokumentacija)}", "Ukupno učitano")
        with d2: kpi_card("Kategorija", f"{dokumentacija['KATEGORIJA'].replace('', pd.NA).dropna().nunique()}", "Različitih")
        with d3: kpi_card("Word/PDF", f"{dokumentacija['TIP'].replace('', pd.NA).dropna().nunique()}", "Tipova dokumenata")
        with d4: kpi_card("Sa linkom", f"{int(dokumentacija['LINK'].astype(str).str.startswith('http').sum())}", "Spremno za otvaranje")

        f1, f2, f3 = st.columns([1.35, 0.85, 0.85])
        with f1:
            search_doc = st.text_input("Pretraži dokumentaciju", "", placeholder="Naziv, alat, mašina, opis, kategorija...")
        with f2:
            kategorije = ["Sve"] + sorted([x for x in dokumentacija["KATEGORIJA"].dropna().astype(str).unique() if x.strip()])
            kat_sel = st.selectbox("Kategorija", kategorije)
        with f3:
            alati_docs = ["Sve"] + sorted([x for x in dokumentacija["ALAT_MASINA"].dropna().astype(str).unique() if x.strip()])
            alat_doc_sel = st.selectbox("Mašina / alat", alati_docs)

        prikaz_docs = dokumentacija.copy()
        # Ako postoji kolona Aktivno i piše NE, sakrij po defaultu.
        if "AKTIVNO" in prikaz_docs.columns:
            prikaz_docs = prikaz_docs[~prikaz_docs["AKTIVNO"].astype(str).str.upper().isin(["NE", "NO", "0", "FALSE", "N"])]
        if kat_sel != "Sve":
            prikaz_docs = prikaz_docs[prikaz_docs["KATEGORIJA"] == kat_sel]
        if alat_doc_sel != "Sve":
            prikaz_docs = prikaz_docs[prikaz_docs["ALAT_MASINA"] == alat_doc_sel]
        if search_doc:
            q = search_doc.lower().strip()
            prikaz_docs = prikaz_docs[
                prikaz_docs.astype(str).apply(lambda col: col.str.lower().str.contains(q, na=False)).any(axis=1)
            ]

        st.markdown("### Kartice dokumenata")
        if prikaz_docs.empty:
            st.info("Nema dokumenata za izabrane filtere.")
        else:
            for _, row in prikaz_docs.iterrows():
                naziv = str(row.get("NAZIV", "Dokument bez naziva"))
                kategorija = str(row.get("KATEGORIJA", ""))
                tip = str(row.get("TIP", "Word"))
                link = str(row.get("LINK", ""))
                opis = str(row.get("OPIS", ""))
                alat = str(row.get("ALAT_MASINA", ""))
                jezik = str(row.get("JEZIK", ""))
                datum = str(row.get("DATUM", ""))

                st.markdown(
                    f"""
                    <div class="kanban-item">
                        <div class="kanban-item-title">📄 {naziv}</div>
                        <div class="kanban-item-meta">
                            Kategorija: <b>{kategorija}</b> &nbsp; | &nbsp;
                            Tip: <b>{tip}</b> &nbsp; | &nbsp;
                            Mašina/alat: <b>{alat}</b> &nbsp; | &nbsp;
                            Jezik: <b>{jezik}</b> &nbsp; | &nbsp;
                            Datum: <b>{datum}</b>
                        </div>
                        <div class="kanban-item-meta">{opis}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if link.startswith("http"):
                    st.link_button("Otvori dokument", link, width="content")
                else:
                    st.caption("Nema validnog linka za ovaj dokument.")

        with st.expander("Tabela dokumentacije"):
            show_dark_dataframe(prikaz_docs, width="stretch", height=450)

        with st.expander("Provera učitavanja DOKUMENTACIJA"):
            raw_docs = ucitaj_dokumentaciju_raw_sheet()
            st.write("Kolone koje je program našao u tabu DOKUMENTACIJA:")
            st.write(list(raw_docs.columns) if not raw_docs.empty else [])
            st.write("Standardizovan prikaz koji program koristi:")
            show_dark_dataframe(dokumentacija.head(20), width="stretch")

    st.markdown('</div>', unsafe_allow_html=True)

if selected_page == '🤖 AI analiza':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Priprema podataka za ChatGPT analizu")
    st.caption("Prva verzija ne šalje ništa automatski. Kopiraš tekst i pošalješ meni u chat.")

    top_alati_txt = ""
    if not analitika.empty:
        for _, r in analitika.head(10).iterrows():
            top_alati_txt += f"- {r['ALAT']}: kvarova {int(r['BROJ_KVAROVA'])}, zastoj {r['ZASTOJ_MIN']:.0f} min, kvarova/1M {r['KVAROVA_NA_1M_UDARACA']:.2f}, status {r['STATUS']}\n"

    top_kategorije_txt = ""
    if not kvarovi_f.empty:
        kat = kvarovi_f.groupby("KATEGORIJA", as_index=False).size().rename(columns={"size": "BROJ"}).sort_values("BROJ", ascending=False)
        for _, r in kat.head(10).iterrows():
            top_kategorije_txt += f"- {r['KATEGORIJA']}: {int(r['BROJ'])} slučajeva\n"

    preventiva_txt = ""
    if not preventiva_status_f.empty:
        prev_alarm = preventiva_status_f[preventiva_status_f["STATUS_PREVENTIVE"].isin(["🔴 Za preventivu", "🟡 Blizu preventive", "⚪ Postavi početno stanje"])].head(15)
        for _, r in prev_alarm.iterrows():
            preventiva_txt += f"- {r['ALAT']}: {r['STATUS_PREVENTIVE']}, lifetime {r['LIFETIME_UDARCI']:.0f}, od preventive {r['UDARCI_OD_PREVENTIVE']:.0f}, ostalo {r['OSTALO_DO_PREVENTIVE']:.0f}, interval {r['INTERVAL_PREVENTIVE']:.0f}, zona {r['ZONA_ZIVOTA']}\n"

    delovi_txt = ""
    if not grupisani_delovi.empty:
        alarms = grupisani_delovi[grupisani_delovi["STATUS"].isin(["🔴 Nema", "🟡 Ispod minimuma"])].head(15)
        for _, r in alarms.iterrows():
            delovi_txt += f"- {r['NAZIV']}: stanje {r['UKUPNO_STANJE']}, minimum {r['MINIMUM']}, lokacije {r['LOKACIJE']}, status {r['STATUS']}\n"

    period_txt = "svi podaci"
    if period and isinstance(period, tuple) and len(period) == 2:
        period_txt = f"{period[0]} - {period[1]}"

    ai_text = f"""Analiziraj podatke za alatnicu i predloži kratkoročne i dugoročne akcije.

PROGRAM: Tooling Control Tower
PERIOD KVAROVA: {period_txt}
MESECI UDARACA: {', '.join(izabrani_meseci) if izabrani_meseci else 'svi'}

OSNOVNI KPI:
- Ukupno kvarova: {ukupno_kvarova}
- Ukupno zastoja: {ukupno_zastoj:.0f} min ({ukupno_zastoj/60:.1f} h)
- MTTR ukupno: {mttr_ukupno:.1f} min
- Ukupno udaraca: {ukupno_udaraca}
- Kritični alati: {kriticni_broj}

TOP ALATI:
{top_alati_txt if top_alati_txt else '- Nema podataka'}

NAJČEŠĆE KATEGORIJE KVAROVA:
{top_kategorije_txt if top_kategorije_txt else '- Nema podataka'}

PREVENTIVNO ODRŽAVANJE:
{preventiva_txt if preventiva_txt else '- Nema alarma za preventivu ili nema podataka'}

REZERVNI DELOVI U ALARMU:
{delovi_txt if delovi_txt else '- Nema podataka ili nema alarmnih delova'}

ZADATAK:
1. Napiši kratak zaključak za sastanak.
2. Izdvoj 3 najkritičnija problema.
3. Predloži kratkoročne akcije za narednih 7 dana.
4. Predloži dugoročne preventivne akcije.
5. Navedi šta treba pratiti na TV panelu naredne nedelje.
"""
    st.text_area("Tekst za slanje u ChatGPT", value=ai_text, height=520)
    st.markdown('</div>', unsafe_allow_html=True)

if selected_page == '🗄️ Sirovi podaci':
    st.markdown('<div class="section-card">', unsafe_allow_html=True)
    st.subheader("Kvarovi - sirovi podaci")
    show_dark_dataframe(kvarovi, width="stretch", height=360)
    st.subheader("Udarci - mesečni zbirni podaci")
    show_dark_dataframe(udarci, width="stretch", height=360)
    st.subheader("Udarci - dnevni podaci")
    show_dark_dataframe(udarci_dnevno, width="stretch", height=360)
    st.subheader("Total punch - lifetime udarci")
    show_dark_dataframe(total_punch_lifetime, width="stretch", height=360)
    st.subheader("Preventiva - istorija")
    show_dark_dataframe(preventiva_istorija, width="stretch", height=360)
    st.subheader("Rezervni delovi - BAZA A")
    show_dark_dataframe(delovi, width="stretch", height=360)
    st.markdown('</div>', unsafe_allow_html=True)
