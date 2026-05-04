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
from datetime import datetime
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

# --- UI DESIGN (CSS) ---
st.markdown("""
<style>
    .empfehlung-card { padding: 25px 20px; border-radius: 12px; text-align: center; margin-bottom: 25px; border: 3px solid #333; }
    .tanken-jetzt { background-color: #28a745; color: white; border-color: #1e7e34; }
    .warten-später { background-color: #ffc107; color: #333; border-color: #d39e00; }
    .zeit-pill { display: inline-block; background: rgba(0,0,0,0.15); padding: 8px 20px; border-radius: 30px; font-size: 1.1rem; font-weight: bold; margin-top: 15px; border: 1px solid rgba(255,255,255,0.3); }
    .analyse-box { background-color: #f8f9fa; border-left: 5px solid #00fbff; padding: 20px; border-radius: 8px; margin-bottom: 20px; color: #333; }
    .rechenweg-zeile { display: flex; justify-content: space-between; padding: 5px 0; border-bottom: 1px dashed #ccc; font-family: monospace; }
    .rechenweg-zeile:last-child { border-bottom: none; font-weight: bold; border-top: 2px solid #333; margin-top: 10px; padding-top: 10px; }
    .accuracy-badge { display: inline-block; padding: 4px 10px; background-color: #e9ecef; border-radius: 5px; font-size: 0.85rem; color: #495057; margin-bottom: 10px; border: 1px solid #ced4da; }
    .totem-mast { background: #111; color: white; border-radius: 12px; max-width: 500px; margin: 20px auto; padding: 10px; }
    .mast-row { display: flex; justify-content: space-between; padding: 12px 15px; border-bottom: 1px solid #333; }
</style>
""", unsafe_allow_html=True)

# --- FUNKTIONEN ---
def hole_gcp_creds():
    gcp_secret = hole_secret("GCP_SERVICE_ACCOUNT")
    if not gcp_secret: return None
    try: return json.loads(gcp_secret) if isinstance(gcp_secret, str) else dict(gcp_secret)
    except: return None

def hole_google_sheet_daten():
    creds_dict = hole_gcp_creds()
    if not creds_dict: return None
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1
        return sheet.get_all_values()
    except: return None

def berechne_erfolgsquote(daten, sorte):
    if not daten or len(daten) < 10: return None, "Noch nicht genug Daten."
    treffer, total = 0, 0
    # Spalten laut Screenshot: A:Zeit, C:Sorte, D:Preis, E:KI_Ziel
    for i in range(1, len(daten) - 10): 
        row = daten[i]
        try:
            if len(row) >= 5 and str(row[2]).lower() == sorte.lower():
                aktuell = float(str(row[3]).replace(',', '.'))
                # Nur prüfen, wenn ein Zielpreis in Spalte E steht
                ziel_str = str(row[4]).strip().replace(',', '.')
                if not ziel_str or ziel_str == "" or ziel_str == "Warten...": continue
                
                ziel = float(ziel_str)
                if ziel < aktuell: # Die KI hat einen Preisabfall vorhergesagt
                    total += 1
                    hit = False
                    # Prüfen, ob dieser Preis in den nächsten 15 Einträgen erreicht wurde
                    for j in range(i + 1, min(i + 15, len(daten))):
                        future_row = daten[j]
                        if str(future_row[2]).lower() == sorte.lower():
                            f_preis = float(str(future_row[3]).replace(',', '.'))
                            if f_preis <= (ziel + 0.005):
                                hit = True
                                break
                    if hit: treffer += 1
        except: continue
    if total == 0: return None, "Keine Vorhersagen zum Vergleichen gefunden."
    return int((treffer / total) * 100), f"{treffer} von {total}"

def hole_koordinaten(ort):
    try:
        if ort.isdigit() and len(ort) == 5:
            r = requests.get(f"https://api.zippopotam.us/de/{ort}", timeout=5)
            if r.status_code == 200:
                d = r.json()
                return float(d['places'][0]['latitude']), float(d['places'][0]['longitude'])
        loc = Nominatim(user_agent="tanktip_v4").geocode(f"{ort}, Deutschland")
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except: return (None, None)

def hole_marktpreis(ticker):
    try: return round(yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1], 2)
    except: return None

def hole_tankstellen(lat, lng, rad, sorte):
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat={lat}&lng={lng}&rad={rad}&sort=price&type={sorte}&apikey={TK_KEY}"
    try: return requests.get(url, timeout=10).json().get("stations", [])
    except: return []

def ki_news_check():
    if not GM_KEY: return "NEUTRAL", "Gemini-API fehlt."
    try:
        r = requests.get("https://finance.yahoo.com/news/rssindex", headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
        feed = feedparser.parse(r.content)
        headlines = " ".join([e.title for e in feed.entries[:15]])
        genai.configure(api_key=GM_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        res = model.generate_content(f"Schlagzeilen: {headlines}. Antworte EXAKT: TREND|GRUND (max 10 Worte Grund).").text.strip().split("|")
        return (res[0].upper(), res[1]) if len(res) == 2 else ("NEUTRAL", "Markt stabil.")
    except: return "NEUTRAL", "News laden..."

# --- HAUPT-ANSICHT ---
try: st.image("TankTip.png", use_container_width=True)
except: st.title("TankTip")

st.markdown("<h4 style='text-align: center; color: gray;'>Moin, lass uns den besten Zeitpunkt zum Tanken finden!</h4>", unsafe_allow_html=True)
st.write("") 

col1, col2 = st.columns(2)
with col1: ort_in = st.text_input("📍 PLZ eingeben:", "24837")
with col2: srt_in = st.selectbox("⛽ Kraftstoff:", ["diesel", "e5", "e10"])

if st.button("🔍 MARKT-ANALYSE STARTEN", use_container_width=True):
    with st.spinner("KI analysiert Markt und Historie..."):
        lat, lng = hole_koordinaten(ort_in)
        if lat:
            stationen = sorted([s for s in hole_tankstellen(lat, lng, 5, srt_in) if s.get('price')], key=lambda x: x['price'])
            if stationen:
                best = stationen[0]
                sheet_daten = hole_google_sheet_daten()
                ki_ziel, ki_msg = None, "Standardwert wird genutzt (-4ct)"
                if sheet_daten:
                    for row in reversed(sheet_daten):
                        if len(row) >= 5 and str(row[2]).lower() == srt_in.lower():
                            val = str(row[4]).strip().replace(',', '.')
                            if val and val not in ["", "Warten..."]:
                                try: ki_ziel, ki_msg = float(val), "KI-Daten live aus Google Sheet"; break
                                except: pass
                if ki_ziel is None: ki_ziel = best['price'] - 0.04

                # STRIKTE LOGIK & ZEIT-TIPP
                jetzt = best['price'] <= ki_ziel
                stunde = datetime.now().hour
                if jetzt: zeit_txt = "⏳ Optimales Fenster: SOFORT"
                elif stunde < 17: zeit_txt = "⏳ Tipp: Warte auf den Abend (meist ab 18-21 Uhr am günstigsten)"
                elif 17 <= stunde < 21: zeit_txt = "⏳ Tipp: Preise fallen oft noch bis 21 Uhr. Etwas Geduld!"
                else: zeit_txt = "⏳ Tipp: Preise ziehen nachts an. Lieber morgen Nachmittag tanken."

                # UI AUSGABE
                trend, news_msg = ki_news_check()
                if trend == "STEIGEND": st.warning(f"📈 **Langfrist-Trend:** {news_msg}")
                elif trend == "FALLEND": st.success(f"📉 **Langfrist-Trend:** {news_msg}")
                else: st.info(f"⚖️ **Langfrist-Trend:** {news_msg}")

                st.markdown(f'<div class="empfehlung-card {"tanken-jetzt" if jetzt else "warten-später"}">'
                            f'<div style="text-transform: uppercase; font-size: 0.9rem;">KI Strategie-Modell</div>'
                            f'<div style="font-size: 2.5rem; font-weight: 900; margin: 5px 0;">{"JETZT TANKEN" if jetzt else "AUF ZIELPREIS WARTEN"}</div>'
                            f'<div class="zeit-pill">{zeit_txt}</div></div>', unsafe_allow_html=True)

                fig = go.Figure(go.Indicator(mode="gauge+number", value=best['price'],
                    gauge={'axis': {'range': [best['price']-0.1, best['price']+0.1]}, 'bar': {'color': "black"},
                           'steps': [{'range': [0, ki_ziel], 'color': "#28a745"}, {'range': [ki_ziel, 5], 'color': "#dc3545"}],
                           'threshold': {'line': {'color': "cyan", 'width': 4}, 'value': ki_ziel}}))
                fig.update_layout(height=230, margin=dict(t=0, b=0))
                st.plotly_chart(fig, use_container_width=True)

                st.markdown(f'<div class="analyse-box"><div class="accuracy-badge">🎯 {ki_msg}</div>'
                            f'<div class="rechenweg-zeile"><span>Bestpreis ({best["brand"]})</span><span>{best["price"]:.3f} €</span></div>'
                            f'<div class="rechenweg-zeile"><span>KI-Ziel für heute</span><span>{ki_ziel:.3f} €</span></div></div>', unsafe_allow_html=True)

                # ERFOLGSQUOTE
                quote, q_msg = berechne_erfolgsquote(sheet_daten, srt_in)
                with st.expander("📊 Hat die KI recht? (Erfolgsquote)"):
                    if quote is not None:
                        st.metric("Treffsicherheit", f"{quote}%")
                        st.write(f"Das Muster wurde in **{q_msg}** Fällen korrekt erkannt.")
                        st.progress(quote / 100)
                    else: st.info(f"Info: {q_msg} (Prüfe Spalte E in Google Sheets)")

                mast = '<div class="totem-mast">'
                for i, s in enumerate(stationen[:3]):
                    c = "#28a745" if i == 0 else "#ffc107" if i == 1 else "#dc3545"
                    mast += f'<div class="mast-row"><div><b>{s["brand"]}</b><br><small>{s.get("dist")} km</small></div>' \
                            f'<div style="color:{c}; font-size: 1.6rem; font-weight: bold;">{s["price"]:.3f}</div></div>'
                st.markdown(mast + '</div>', unsafe_allow_html=True)
            else: st.error("Keine Tankstellen gefunden.")

# --- FOOTER ---
st.write("---")
with st.expander("🛡️ System-Status & Diagnosedaten"):
    if hole_gcp_creds(): st.success("✅ Google Cloud API verbunden")
    oel = hole_marktpreis("BZ=F")
    if oel: st.metric("Globaler Ölpreis (Brent)", f"{oel} $")
