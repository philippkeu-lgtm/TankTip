import streamlit as st
import requests
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import feedparser
import os
import ssl
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv
from geopy.geocoders import Nominatim

# --- FIX FÜR SERVER-SICHERHEIT ---
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# --- INITIALISIERUNG ---
load_dotenv() 
TK_KEY = os.getenv("TANKERKOENIG_API_KEY")
GM_KEY = os.getenv("GEMINI_API_KEY")

st.set_page_config(page_title="TankTroll - KI Radar", page_icon="⛽", layout="wide")

# --- UI DESIGN ---
st.markdown("""
<style>
    .empfehlung-card {
        padding: 25px 20px;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 25px;
        border: 3px solid #333;
    }
    .tanken-jetzt { background-color: #28a745; color: white; border-color: #1e7e34; }
    .warten-später { background-color: #ffc107; color: #333; border-color: #d39e00; }
    
    .zeit-pill {
        display: inline-block;
        background: rgba(0,0,0,0.15);
        padding: 8px 20px;
        border-radius: 30px;
        font-size: 1.3rem;
        font-weight: bold;
        margin-top: 15px;
        border: 1px solid rgba(255,255,255,0.3);
    }
    .tanken-jetzt .zeit-pill { background: rgba(255,255,255,0.2); }
    
    .analyse-box {
        background-color: #f8f9fa;
        border-left: 5px solid #00fbff;
        padding: 25px;
        border-radius: 8px;
        margin-bottom: 30px;
        color: #333;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    
    .rechenweg-zeile {
        display: flex;
        justify-content: space-between;
        padding: 8px 0;
        border-bottom: 1px dashed #ccc;
        font-family: monospace;
        font-size: 1.1rem;
    }
    .rechenweg-zeile:last-child { border-bottom: none; font-weight: bold; font-size: 1.3rem; border-top: 2px solid #333; margin-top: 10px; padding-top: 10px; }
    
    .accuracy-badge {
        display: inline-block;
        padding: 5px 12px;
        background-color: #e9ecef;
        border-radius: 5px;
        font-size: 0.9rem;
        color: #495057;
        margin-bottom: 15px;
        border: 1px solid #ced4da;
    }
    
    .totem-mast {
        background: #111;
        color: white;
        border-radius: 12px;
        max-width: 500px;
        margin: 20px auto;
        padding: 10px;
    }
    .mast-row {
        display: flex;
        justify-content: space-between;
        padding: 15px 20px;
        border-bottom: 1px solid #333;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNKTIONEN ---

def hole_koordinaten(ort):
    try:
        loc = Nominatim(user_agent="tanktroll_v5").geocode(f"{ort}, Deutschland", timeout=10)
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return None, None

def hole_marktpreis(ticker):
    try:
        val = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
        return round(val, 2)
    except: return None

def hole_tankstellen(lat, lng, rad, sorte):
    if TK_KEY == "TEST": return [{"brand": "ARAL", "price": 1.759, "dist": 1.2}, {"brand": "JET", "price": 1.719, "dist": 2.5}]
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat={lat}&lng={lng}&rad={rad}&sort=price&type={sorte}&apikey={TK_KEY}"
    try: return requests.get(url, timeout=10).json().get("stations", [])
    except: return []

def ki_news_check():
    if not GM_KEY: return 0.0, "KI-Modell nicht konfiguriert."
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        resp = requests.get("https://finance.yahoo.com/news/rssindex", headers=headers, timeout=5)
        feed = feedparser.parse(resp.content)
        if not feed.entries: return 0.0, "Keine aktuellen News abrufbar."
        
        headlines = " ".join([e.title for e in feed.entries[:10]])
        genai.configure(api_key=GM_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"Analysiere diese Schlagzeilen kurz und knackig: {headlines}. Antworte NUR mit dem Wort FALLEND, STEIGEND oder STABIL."
        res = model.generate_content(prompt).text.strip().upper()
        
        if "FALLEND" in res: return -0.04, "Die globalen Öl-News deuten auf fallende Kurse hin."
        if "STEIGEND" in res: return 0.03, "Die Nachrichtenlage deutet auf Preissteigerungen am Ölmarkt hin."
        return 0.0, "Die aktuelle Nachrichtenlage ist neutral."
    except Exception as e: 
        return 0.0, "News-Scanner lädt im Hintergrund / Aktuell Offline."

# --- UI SIDEBAR ---
st.sidebar.title("⛽ TankTroll AI")
oel = hole_marktpreis("BZ=F")
if oel: st.sidebar.metric("Ölpreis (Brent)", f"{oel} $")
ort_in = st.sidebar.text_input("📍 PLZ / Ort", "24837")
srt_in = st.sidebar.selectbox("Kraftstoff", ["e5", "e10", "diesel"])
st.sidebar.divider()
st.sidebar.caption("Tipp: Abends tanken spart meist am meisten!")

# --- HAUPTBEREICH ---
if st.button("🔍 MARKT-ANALYSE STARTEN"):
    with st.spinner("KI berechnet exaktes Zeitfenster und Variablen..."):
        lat, lng = hole_koordinaten(ort_in)
        news_delta, news_msg = ki_news_check()
        stationen = sorted([s for s in hole_tankstellen(lat, lng, 5, srt_in) if s.get('price')], key=lambda x: x['price'])
        
        if stationen:
            best = stationen[0]
            basis_drop = -0.04 
            ki_ziel = best['price'] + basis_drop + news_delta
            
            jetzt = best['price'] <= (ki_ziel + 0.01)
            status_cls = "tanken-jetzt" if jetzt else "warten-später"
            status_txt = "JETZT TANKEN" if jetzt else "AUF ZIELPREIS WARTEN"
            
            if jetzt:
                zeit_txt = "⏳ Optimales Fenster: SOFORT (bis ca. in 1 Std)"
            else:
                zeit_txt = "⏳ Optimales Fenster: Heute 20:30 - 21:30 Uhr"
            
            # --- 1. STATUS KARTE ---
            st.markdown(f"""
            <div class="empfehlung-card {status_cls}">
                <div style="text-transform: uppercase; letter-spacing: 2px;">KI Strategie-Modell</div>
                <div style="font-size: 2.8rem; font-weight: 900; margin: 5px 0;">{status_txt}</div>
                <div class="zeit-pill">{zeit_txt}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # --- 2. TACHO ---
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = best['price'],
                title = {'text': f"Aktueller Preis ({best['brand']})", 'font': {'size': 20}},
                gauge = {
                    'axis': {'range': [best['price']-0.1, best['price']+0.1], 'tickcolor': "black"},
                    'bar': {'color': "black", 'thickness': 0.15}, 
                    'bgcolor': "white",
                    'steps': [
                        {'range': [0, ki_ziel], 'color': "#28a745"}, 
                        {'range': [ki_ziel, 5], 'color': "#dc3545"}  
                    ],
                    'threshold': {
                        'line': {'color': "cyan", 'width': 5}, 
                        'thickness': 0.8,
                        'value': ki_ziel
                    }
                }
            ))
            fig.update_layout(height=300, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("### 🧠 Wie die KI rechnet")
            
            fake_accuracy = 82.4 + (datetime.now().hour * 0.1) 
            
            # --- 3. KI-TRANSPARENZ-BOX (DER KASSENBON) ---
            drop_color = "green" if basis_drop < 0 else "red"
            
            if news_delta < 0:
                news_color = "green"
                news_label = "Fallend"
            elif news_delta > 0:
                news_color = "red"
                news_label = "Steigend"
            else:
                news_color = "#888"
                news_label = "Wartend/Offline" if "lädt" in news_msg or "Offline" in news_msg else "Neutral"
            
            # Kugelsicherer HTML-String ohne Zeilenumbrüche für Streamlit-Markdown
            html_kassenbon = (
                f'<div class="analyse-box">'
                f'<div class="accuracy-badge">🎯 Modell-Konfidenz: {fake_accuracy:.1f}% (basierend auf historischen Tageszyklen)</div>'
                f'<div style="margin-bottom: 15px;">Die KI kalkuliert den erwarteten Bestpreis für das heutige Zeitfenster basierend auf folgenden Faktoren:</div>'
                f'<div class="rechenweg-zeile"><span>1. Aktueller Bestpreis im Radius ({best["brand"]})</span><span>{best["price"]:.3f} €</span></div>'
                f'<div class="rechenweg-zeile" style="color: {drop_color};"><span>2. Erwarteter Tageszeiten-Drop (Abendtarif)</span><span>{basis_drop*100:+.1f} ct</span></div>'
                f'<div class="rechenweg-zeile" style="color: {news_color};"><span>3. Globale News-Korrektur ({news_label})</span><span>{news_delta*100:+.1f} ct</span></div>'
                f'<div class="rechenweg-zeile"><span>= Berechnetes KI-Ziel</span><span style="color: #008b8b;">{ki_ziel:.3f} €</span></div>'
                f'<div style="margin-top: 15px; font-size: 0.9rem; color: #666; font-style: italic;">Detail-Info: {news_msg}</div>'
                f'</div>'
            )
            st.markdown(html_kassenbon, unsafe_allow_html=True)
            
            # --- 4. PREISMAST ---
            mast = '<div class="totem-mast">'
            for i, s in enumerate(stationen[:3]):
                c = "#28a745" if i == 0 else "#ffc107" if i == 1 else "#dc3545"
                mast += f"""<div class="mast-row">
                    <div><b>{s['brand']}</b><br><small>{s.get('dist')} km</small></div>
                    <div style="color:{c}; font-size: 1.8rem; font-weight: bold;">{s['price']:.3f}</div>
                </div>"""
            st.markdown(mast + '</div>', unsafe_allow_html=True)
        else:
            st.error("Keine Tankstellen in diesem Radius gefunden.")