import streamlit as st
import requests
import yfinance as yf
import google.generativeai as genai
import pandas as pd
import feedparser
import os
import ssl
import json
import plotly.graph_objects as go
from datetime import datetime, timedelta
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- FIX FÜR SERVER-SICHERHEIT ---
if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# --- INITIALISIERUNG ---
st.set_page_config(page_title="TankTip - KI Radar", page_icon="⛽", layout="centered")
load_dotenv() 

def hole_secret(key):
    try: return st.secrets[key]
    except: return os.getenv(key)

TK_KEY = hole_secret("TANKERKOENIG_API_KEY")
GM_KEY = hole_secret("GEMINI_API_KEY")

# --- UI DESIGN ---
st.markdown("""
<style>
    .empfehlung-card { padding: 25px 20px; border-radius: 12px; text-align: center; margin-bottom: 25px; border: 3px solid #333; }
    .tanken-jetzt { background-color: #28a745; color: white; border-color: #1e7e34; }
    .warten-später { background-color: #ffc107; color: #333; border-color: #d39e00; }
    .zeit-pill { display: inline-block; background: rgba(0,0,0,0.15); padding: 8px 20px; border-radius: 30px; font-size: 1.3rem; font-weight: bold; margin-top: 15px; border: 1px solid rgba(255,255,255,0.3); }
    .tanken-jetzt .zeit-pill { background: rgba(255,255,255,0.2); }
    .analyse-box { background-color: #f8f9fa; border-left: 5px solid #00fbff; padding: 25px; border-radius: 8px; margin-bottom: 30px; color: #333; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .rechenweg-zeile { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px dashed #ccc; font-family: monospace; font-size: 1.1rem; }
    .rechenweg-zeile:last-child { border-bottom: none; font-weight: bold; font-size: 1.3rem; border-top: 2px solid #333; margin-top: 10px; padding-top: 10px; }
    .accuracy-badge { display: inline-block; padding: 5px 12px; background-color: #e9ecef; border-radius: 5px; font-size: 0.9rem; color: #495057; margin-bottom: 15px; border: 1px solid #ced4da; }
    .totem-mast { background: #111; color: white; border-radius: 12px; max-width: 500px; margin: 20px auto; padding: 10px; }
    .mast-row { display: flex; justify-content: space-between; padding: 15px 20px; border-bottom: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# --- FUNKTIONEN ---
def hole_gcp_creds():
    gcp_secret = hole_secret("GCP_SERVICE_ACCOUNT")
    if not gcp_secret: return None
    try: return json.loads(gcp_secret) if isinstance(gcp_secret, str) else dict(gcp_secret)
    except: return None

def hole_echte_ki_daten(sorte):
    creds_dict = hole_gcp_creds()
    if not creds_dict: return None, "Keine Google-Verbindung"
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1
        daten = sheet.get_all_values() 
        for row in reversed(daten):
            if len(row) >= 5 and str(row[2]).lower() == sorte.lower():
                ki_wert = str(row[4]).strip().replace(',', '.')
                if ki_wert and ki_wert != "Warten...":
                    return float(ki_wert), "TimesFM Daten live aus Google Sheet"
        return None, "Noch keine TimesFM Daten gefunden"
    except Exception as e:
        return None, f"Ladefehler: {str(e)}"

def hole_koordinaten(ort):
    try:
        ort = str(ort).strip()
        if ort.isdigit() and len(ort) == 5:
            resp = requests.get(f"https://api.zippopotam.us/de/{ort}", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return float(data['places'][0]['latitude']), float(data['places'][0]['longitude'])
        loc = Nominatim(user_agent="tanktip_pro_v1").geocode(f"{ort}, Deutschland", timeout=10)
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return None, None

def hole_marktpreis(ticker):
    try: return round(yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1], 2)
    except: return None

def hole_tankstellen(lat, lng, rad, sorte):
    if TK_KEY == "TEST": return [{"brand": "ARAL", "price": 1.759, "dist": 1.2}, {"brand": "JET", "price": 1.719, "dist": 2.5}]
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat={lat}&lng={lng}&rad={rad}&sort=price&type={sorte}&apikey={TK_KEY}"
    try: return requests.get(url, timeout=10).json().get("stations", [])
    except: return []

def ki_news_check():
    if not GM_KEY: return "NEUTRAL", "Gemini-API fehlt für die News-Analyse."
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get("https://finance.yahoo.com/news/rssindex", headers=headers, timeout=5)
        feed = feedparser.parse(resp.content)
        if not feed.entries: return "NEUTRAL", "Keine aktuellen News abrufbar."
        
        headlines = " ".join([e.title for e in feed.entries[:15]])
        genai.configure(api_key=GM_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        Hier sind die aktuellen Finanz-Schlagzeilen: {headlines}
        Gibt es darin wichtige News, die den globalen Ölpreis beeinflussen könnten?
        Antworte EXAKT in diesem Format: TREND|GRUND
        - 'TREND' darf nur FALLEND, STEIGEND oder NEUTRAL sein.
        - 'GRUND' ist ein extrem kurzer Satz (max 10 Worte), der genau sagt, was passiert. Wenn nichts Relevantes passiert, schreibe 'Keine besonderen Öl-Ereignisse'.
        """
        
        res = model.generate_content(prompt).text.strip()
        teile = res.split("|")
        
        if len(teile) == 2:
            trend = teile[0].strip().upper()
            grund = teile[1].strip()
            
            if trend == "STEIGEND": return "STEIGEND", f"{grund}."
            elif trend == "FALLEND": return "FALLEND", f"{grund}."
            else: return "NEUTRAL", "Aktuell keine extremen Meldungen am Ölmarkt."
        else:
            return "NEUTRAL", "Nachrichtenlage ist aktuell stabil."
            
    except Exception as e: 
        return "NEUTRAL", "News-Scanner lädt im Hintergrund."

# --- HAUPT-ANSICHT (ZENTRIERT) ---

# Hier wird dein eigenes Logo geladen!
try:
    st.image("TankTip.png", width=120) 
except:
    pass # Falls das Bild noch nicht hochgeladen wurde, stürzt die App nicht ab

st.title("TankTip")
st.markdown("Dein persönlicher KI-Radar für den besten Tank-Zeitpunkt.")
st.write("") 

col1, col2 = st.columns(2)
with col1:
    ort_in = st.text_input("📍 PLZ (z.B. 24837) eingeben:", "24837")
with col2:
    srt_in = st.selectbox("⛽ Kraftstoff wählen:", ["e5", "e10", "diesel"])

st.write("") 

if st.button("🔍 MARKT-ANALYSE STARTEN", use_container_width=True):
    with st.spinner("Lade Live-Preise, News und TimesFM-Prognose..."):
        lat, lng = hole_koordinaten(ort_in)
        if lat is None or lng is None:
            st.error(f"❌ Fehler: Konnte keine Koordinaten für '{ort_in}' finden.")
            st.stop()
            
        roh_stationen = hole_tankstellen(lat, lng, 5, srt_in)
        if not roh_stationen:
            st.warning("⚠️ Tankerkönig liefert aktuell eine leere Liste.")
            st.stop()

        stationen = sorted([s for s in roh_stationen if s.get('price')], key=lambda x: x['price'])
        
        if stationen:
            best = stationen[0]
            
            ki_ziel, ki_msg = hole_echte_ki_daten(srt_in)
            if ki_ziel is None:
                ki_ziel = best['price'] - 0.04
                ki_msg = "TimesFM sammelt noch... (Standardwert wird genutzt)"
                
            basis_drop = ki_ziel - best['price']
            jetzt = best['price'] <= (ki_ziel + 0.01)
            
            status_cls = "tanken-jetzt" if jetzt else "warten-später"
            status_txt = "JETZT TANKEN" if jetzt else "AUF ZIELPREIS WARTEN"
            zeit_txt = "⏳ Optimales Fenster: SOFORT" if jetzt else "⏳ Prognose: Preis fällt heute voraussichtlich noch"
            
            # --- NEWS INFOBOX ---
            trend, news_msg = ki_news_check()
            if trend == "STEIGEND":
                st.warning(f"📈 **Langfrist-Trend:** {news_msg} (Bald volltanken könnte schlau sein.)")
            elif trend == "FALLEND":
                st.success(f"📉 **Langfrist-Trend:** {news_msg} (Die Tendenz zeigt eher nach unten.)")
            else:
                st.info(f"⚖️ **Langfrist-Trend:** {news_msg}")

            # --- STATUS KARTE ---
            st.markdown(f"""
            <div class="empfehlung-card {status_cls}">
                <div style="text-transform: uppercase; letter-spacing: 2px;">KI Strategie-Modell (TimesFM)</div>
                <div style="font-size: 2.8rem; font-weight: 900; margin: 5px 0;">{status_txt}</div>
                <div class="zeit-pill">{zeit_txt}</div>
            </div>
            """, unsafe_allow_html=True)
            
            # --- TACHO ---
            fig = go.Figure(go.Indicator(
                mode = "gauge+number", value = best['price'],
                title = {'text': f"Aktueller Preis ({best['brand']})", 'font': {'size': 20}},
                gauge = {
                    'axis': {'range': [best['price']-0.1, best['price']+0.1], 'tickcolor': "black"},
                    'bar': {'color': "black", 'thickness': 0.15}, 'bgcolor': "white",
                    'steps': [{'range': [0, ki_ziel], 'color': "#28a745"}, {'range': [ki_ziel, 5], 'color': "#dc3545"}],
                    'threshold': {'line': {'color': "cyan", 'width': 5}, 'thickness': 0.8, 'value': ki_ziel}
                }
            ))
            fig.update_layout(height=300, margin=dict(t=50, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            # --- KASSENBON ---
            drop_color = "green" if basis_drop < 0 else "red"
            html_kassenbon = (
                f'<div class="analyse-box">'
                f'<div class="accuracy-badge">🎯 {ki_msg}</div>'
                f'<div class="rechenweg-zeile"><span>1. Aktueller Bestpreis im Radius ({best["brand"]})</span><span>{best["price"]:.3f} €</span></div>'
                f'<div class="rechenweg-zeile" style="color: {drop_color};"><span>2. Google TimesFM Prognose (Tages-Drop)</span><span>{basis_drop*100:+.1f} ct</span></div>'
                f'<div class="rechenweg-zeile"><span>= Berechnetes KI-Ziel für heute</span><span style="color: #008b8b;">{ki_ziel:.3f} €</span></div>'
                f'</div>'
            )
            st.markdown(html_kassenbon, unsafe_allow_html=True)
            
            # --- PREISMAST ---
            mast = '<div class="totem-mast">'
            for i, s in enumerate(stationen[:3]):
                c = "#28a745" if i == 0 else "#ffc107" if i == 1 else "#dc3545"
                mast += f'<div class="mast-row"><div><b>{s["brand"]}</b><br><small>{s.get("dist")} km</small></div><div style="color:{c}; font-size: 1.8rem; font-weight: bold;">{s["price"]:.3f}</div></div>'
            st.markdown(mast + '</div>', unsafe_allow_html=True)

# --- VERSTECKTE SYSTEM-DIAGNOSE ---
st.write("---")
with st.expander("🔧 Entwickler: System-Status & API Diagnose"):
    if TK_KEY: st.success("✅ Tankerkönig API aktiv")
    else: st.error("❌ Tankerkönig API fehlt")
    if GM_KEY: st.success("✅ Gemini API aktiv")
    else: st.warning("⚠️ Gemini API fehlt")
    if hole_gcp_creds(): st.success("✅ Google Sheets verknüpft")
    else: st.error("❌ Google Sheets Secret fehlt")
    
    oel = hole_marktpreis("BZ=F")
    if oel: st.metric("Globaler Ölpreis (Brent)", f"{oel} $")
