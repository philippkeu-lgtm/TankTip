import streamlit as st
import requests
import yfinance as yf
import google.generativeai as genai
import feedparser
import os
import json
import plotly.graph_objects as go
from datetime import datetime
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- INITIALISIERUNG ---
st.set_page_config(page_title="TankTip - KI Radar", page_icon="⛽", layout="centered")
load_dotenv()

def hole_secret(key):
    try:
        return st.secrets[key]
    except:
        return os.getenv(key)

TK_KEY = hole_secret("TANKERKOENIG_API_KEY")
GM_KEY = hole_secret("GEMINI_API_KEY")

# --- UI DESIGN ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Inter:wght@400;600&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .empfehlung-card {
        padding: 28px 20px; border-radius: 14px; text-align: center;
        margin-bottom: 25px; border: 3px solid #333;
    }
    .tanken-jetzt   { background: linear-gradient(135deg,#1a7a3a,#28a745); color: white; border-color: #1e7e34; }
    .fast-am-ziel   { background: linear-gradient(135deg,#b86e00,#ffc107); color: #1a1a1a; border-color: #d39e00; }
    .warten-später  { background: linear-gradient(135deg,#555,#777);       color: white;  border-color: #444; }

    .card-label { text-transform: uppercase; font-size: 0.8rem; letter-spacing: 2px; opacity: 0.85; }
    .card-main  { font-family: 'Bebas Neue', sans-serif; font-size: 3rem; line-height: 1.1; margin: 6px 0; }
    .card-sub   { font-size: 0.95rem; opacity: 0.9; margin-top: 4px; }

    .zeit-pill {
        display: inline-block; background: rgba(0,0,0,0.18);
        padding: 8px 22px; border-radius: 30px; font-size: 1rem;
        font-weight: 600; margin-top: 14px; border: 1px solid rgba(255,255,255,0.25);
    }
    .analyse-box {
        background: #f8f9fa; border-left: 5px solid #00c8cc;
        padding: 20px; border-radius: 10px; margin-bottom: 20px; color: #222;
    }
    .rechenweg-zeile {
        display: flex; justify-content: space-between;
        padding: 6px 0; border-bottom: 1px dashed #ccc; font-family: monospace; font-size: 0.95rem;
    }
    .rechenweg-zeile:last-child {
        border-bottom: none; font-weight: bold;
        border-top: 2px solid #333; margin-top: 10px; padding-top: 10px;
    }
    .accuracy-badge {
        display: inline-block; padding: 4px 12px; background: #e9ecef;
        border-radius: 6px; font-size: 0.82rem; color: #495057;
        margin-bottom: 12px; border: 1px solid #ced4da;
    }
    .totem-mast {
        background: #111; color: white; border-radius: 14px;
        max-width: 500px; margin: 20px auto; padding: 8px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .mast-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 13px 16px; border-bottom: 1px solid #222;
    }
    .mast-row:last-child { border-bottom: none; }
    .trend-banner {
        padding: 10px 16px; border-radius: 8px; margin-bottom: 16px;
        font-weight: 600; font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)


# --- HILFSFUNKTIONEN ---

def hole_gcp_creds():
    gcp_secret = hole_secret("GCP_SERVICE_ACCOUNT")
    if not gcp_secret:
        return None
    try:
        return json.loads(gcp_secret) if isinstance(gcp_secret, str) else dict(gcp_secret)
    except:
        return None

def hole_google_sheet_daten():
    creds_dict = hole_gcp_creds()
    if not creds_dict:
        return None
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1
        return sheet.get_all_values()
    except:
        return None

def hole_ki_ziel(sheet_daten, plz, sorte):
    if not sheet_daten:
        return None, "Keine Sheet-Daten"

    for row in reversed(sheet_daten):
        if len(row) < 5:
            continue
        row_plz  = str(row[1]).strip()
        row_sorte = str(row[2]).strip().lower()
        row_ziel  = str(row[4]).strip().replace(',', '.')

        if row_sorte != sorte.lower():
            continue
        if row_plz and row_plz != plz and row_plz != "":
            continue
        if not row_ziel or row_ziel in ["", "Warten..."]:
            continue
        try:
            return float(row_ziel), "KI-Ziel aus Google Sheet"
        except:
            continue

    return None, "Kein KI-Ziel im Sheet gefunden"

def erstelle_preis_chart(sheet_daten, plz, sorte, ki_ziel):
    """Erstellt einen Plotly-Chart der letzten Preisentwicklungen."""
    if not sheet_daten or len(sheet_daten) < 2:
        return None

    passende_daten = []
    # Wir überspringen den Header (Zeile 0)
    for row in sheet_daten[1:]:
        if len(row) >= 4:
            r_plz = str(row[1]).strip()
            r_sorte = str(row[2]).strip().lower()
            
            if r_sorte == sorte.lower() and (not r_plz or r_plz == plz):
                try:
                    # Versuche das Datum umzuwandeln für eine saubere X-Achse
                    zeit_str = str(row[0])
                    preis = float(str(row[3]).replace(',', '.'))
                    try:
                        dt = datetime.strptime(zeit_str, "%d.%m.%Y %H:%M")
                    except:
                        dt = zeit_str # Fallback auf String
                    passende_daten.append((dt, preis))
                except:
                    continue

    # Nimm die letzten 30 Datenpunkte (ca. 4-5 Tage Historie)
    passende_daten = passende_daten[-30:]
    if len(passende_daten) < 3:
        return None

    x_werte = [d[0] for d in passende_daten]
    y_werte = [d[1] for d in passende_daten]

    fig = go.Figure()
    
    # Preis-Kurve zeichnen
    fig.add_trace(go.Scatter(
        x=x_werte, y=y_werte,
        mode='lines+markers',
        name='Bester Preis',
        line=dict(color='#00c8cc', width=3, shape='spline'),
        marker=dict(size=7, color='#00c8cc')
    ))

    # KI-Ziel als grüne gestrichelte Linie
    if ki_ziel:
        fig.add_hline(
            y=ki_ziel, 
            line_dash="dash", 
            line_color="#28a745", 
            line_width=2,
            annotation_text="KI Zielpreis", 
            annotation_position="bottom right"
        )

    fig.update_layout(
        title=f"Historischer Verlauf ({sorte.upper()})",
        margin=dict(l=10, r=10, t=40, b=10),
        height=280,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.3)', tickformat='.3f', ticksuffix=' €')
    )
    return fig

def berechne_erfolgsquote(daten, sorte):
    if not daten or len(daten) < 10:
        return None, "Noch nicht genug Daten."
    treffer, total = 0, 0
    for i in range(1, len(daten) - 10):
        row = daten[i]
        try:
            if len(row) < 5 or str(row[2]).lower() != sorte.lower():
                continue
            aktuell  = float(str(row[3]).replace(',', '.'))
            ziel_str = str(row[4]).strip().replace(',', '.')
            if not ziel_str or ziel_str in ["", "Warten..."]:
                continue
            ziel = float(ziel_str)
            if ziel >= aktuell:
                continue 

            total += 1
            for j in range(i + 1, min(i + 15, len(daten))):
                fr = daten[j]
                if str(fr[2]).lower() == sorte.lower():
                    if float(str(fr[3]).replace(',', '.')) <= ziel + 0.005:
                        treffer += 1
                        break
        except:
            continue

    if total == 0:
        return None, "Keine auswertbaren Vorhersagen gefunden."
    return int((treffer / total) * 100), f"{treffer} von {total}"

def hole_koordinaten(ort):
    try:
        if ort.isdigit() and len(ort) == 5:
            r = requests.get(f"https://api.zippopotam.us/de/{ort}", timeout=5)
            if r.status_code == 200:
                d = r.json()
                return float(d['places'][0]['latitude']), float(d['places'][0]['longitude'])
        loc = Nominatim(user_agent="tanktip_v6").geocode(f"{ort}, Deutschland")
        return (loc.latitude, loc.longitude) if loc else (None, None)
    except:
        return (None, None)

def hole_marktpreis(ticker):
    try:
        return round(yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1], 2)
    except:
        return None

def hole_tankstellen(lat, lng, rad, sorte):
    url = (
        f"https://creativecommons.tankerkoenig.de/json/list.php"
        f"?lat={lat}&lng={lng}&rad={rad}&sort=price&type={sorte}&apikey={TK_KEY}"
    )
    try:
        return requests.get(url, timeout=10).json().get("stations", [])
    except:
        return []

def ki_news_check():
    if not GM_KEY:
        return "NEUTRAL", "Gemini-API fehlt."
    try:
        r = requests.get(
            "https://finance.yahoo.com/news/rssindex",
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=5
        )
        import feedparser
        feed = feedparser.parse(r.content)
        headlines = " ".join([e.title for e in feed.entries[:15]])
        genai.configure(api_key=GM_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = (
            f"Schlagzeilen: {headlines}\n"
            "Analysiere ob der globale Ölpreis eher steigen oder fallen wird.\n"
            "Antworte EXAKT im Format: TREND|GRUND\n"
            "TREND = STEIGEND, FALLEND oder NEUTRAL\n"
            "GRUND = max. 10 Wörter auf Deutsch"
        )
        res = model.generate_content(prompt).text.strip().split("|")
        if len(res) == 2:
            trend = res[0].strip().upper()
            grund = res[1].strip()
            return trend, grund
        return "NEUTRAL", "Markt stabil."
    except:
        return "NEUTRAL", "News nicht verfügbar."

def empfehlung_berechnen(aktuell, ki_ziel, trend, stunde):
    differenz = aktuell - ki_ziel

    trend_druck = trend == "STEIGEND"

    if differenz <= 0.005 or (trend_druck and differenz <= 0.015):
        stufe = "jetzt"
        css   = "tanken-jetzt"
        haupt = "JETZT TANKEN"
        sub   = f"Preis liegt {'am' if differenz <= 0.005 else 'nahe am'} Tagesziel"
        zeit  = "⏳ Optimales Fenster: SOFORT"

    elif differenz <= 0.020:
        stufe = "fast"
        css   = "fast-am-ziel"
        haupt = "FAST AM ZIEL"
        sub   = f"Noch ~{differenz*100:.1f}ct bis Zielpreis"
        if stunde < 16:
            zeit = "⏳ Tipp: Warte auf den Abend (18-21 Uhr)"
        elif 16 <= stunde < 21:
            zeit = "⏳ Preise fallen oft noch etwas – kurz warten lohnt sich"
        else:
            zeit = "⏳ Nachtpreise steigen – jetzt noch okay zum Tanken"

    else:
        stufe = "warten"
        css   = "warten-später"
        haupt = "AUF ZIELPREIS WARTEN"
        sub   = f"Noch {differenz*100:.1f}ct bis zum Tagesziel"
        if stunde < 16:
            zeit = "⏳ Tipp: Warte auf den Abend (meist ab 18-21 Uhr günstiger)"
        elif 16 <= stunde < 21:
            zeit = "⏳ Preise fallen jetzt aktiv – Geduld zahlt sich aus"
        else:
            zeit = "⏳ Preise ziehen nachts an – lieber morgen Nachmittag tanken"

    return stufe, css, haupt, sub, zeit


# --- HAUPT-UI ---
try:
    st.image("TankTip.png", use_container_width=True)
except:
    st.markdown("<h1 style='text-align:center; font-family: Bebas Neue, sans-serif; font-size: 3rem;'>⛽ TankTip</h1>", unsafe_allow_html=True)

st.markdown(
    "<h4 style='text-align: center; color: #888; font-weight: 400;'>"
    "Moin, lass uns den besten Zeitpunkt zum Tanken finden.</h4>",
    unsafe_allow_html=True
)
st.write("")

col1, col2 = st.columns(2)
with col1:
    ort_in = st.text_input("📍 PLZ eingeben:", "24837")
with col2:
    srt_in = st.selectbox("⛽ Kraftstoff:", ["diesel", "e5", "e10"])

if st.button("🔍 MARKT-ANALYSE STARTEN", use_container_width=True):
    with st.spinner("Lade Preise und analysiere Markt..."):
        lat, lng = hole_koordinaten(ort_in)

        if not lat:
            st.error("PLZ nicht gefunden. Bitte prüfen.")
            st.stop()

        stationen = [s for s in hole_tankstellen(lat, lng, 5, srt_in) if s.get('price')]
        stationen = sorted(stationen, key=lambda x: x['price'])

        if not stationen:
            st.error("Keine Tankstellen in 5km Umkreis gefunden.")
            st.stop()

        best   = stationen[0]
        stunde = datetime.now().hour

        # KI-Ziel laden (PLZ-gefiltert)
        sheet_daten = hole_google_sheet_daten()
        ki_ziel, ki_msg = hole_ki_ziel(sheet_daten, ort_in, srt_in)
        if ki_ziel is None:
            ki_ziel = best['price'] - 0.04
            ki_msg  = "Standardwert (-4ct, kein Sheet-Eintrag für diese PLZ)"

        # News-Trend
        trend, news_msg = ki_news_check()

        # Empfehlung berechnen
        stufe, css, haupt, sub, zeit_txt = empfehlung_berechnen(
            best['price'], ki_ziel, trend, stunde
        )

        # --- TREND BANNER ---
        if trend == "STEIGEND":
            st.warning(f"📈 **Globaler Öl-Trend:** {news_msg} – nicht zu lange warten!")
        elif trend == "FALLEND":
            st.success(f"📉 **Globaler Öl-Trend:** {news_msg}")
        else:
            st.info(f"⚖️ **Globaler Öl-Trend:** {news_msg}")

        # --- EMPFEHLUNGS-KARTE ---
        st.markdown(
            f'<div class="empfehlung-card {css}">'
            f'<div class="card-label">KI Strategie-Modell</div>'
            f'<div class="card-main">{haupt}</div>'
            f'<div class="card-sub">{sub}</div>'
            f'<div class="zeit-pill">{zeit_txt}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # --- GAUGE ---
        gauge_min = round(ki_ziel - 0.05, 3)
        gauge_max = round(best['price'] + 0.05, 3)
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=best['price'],
            number={'suffix': ' €', 'valueformat': '.3f'},
            gauge={
                'axis': {'range': [gauge_min, gauge_max], 'tickformat': '.3f'},
                'bar':  {'color': "#222"},
                'steps': [
                    {'range': [gauge_min, ki_ziel],  'color': "#28a745"},
                    {'range': [ki_ziel,  gauge_max], 'color': "#dc3545"},
                ],
                'threshold': {
                    'line': {'color': "cyan", 'width': 4},
                    'value': ki_ziel
                }
            }
        ))
        fig.update_layout(height=220, margin=dict(t=10, b=0, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True)

        # --- KASSENBON ---
        basis_drop  = ki_ziel - best['price']
        drop_color  = "green" if basis_drop >= 0 else "#cc3300"
        drop_prefix = "+" if basis_drop >= 0 else ""
        st.markdown(f"""
        <div class="analyse-box">
            <div class="accuracy-badge">🎯 {ki_msg}</div>
            <div class="rechenweg-zeile">
                <span>Bester Preis aktuell ({best['brand']})</span>
                <span>{best['price']:.3f} €</span>
            </div>
            <div class="rechenweg-zeile" style="color:{drop_color};">
                <span>Erwarteter Tages-Trend</span>
                <span>{drop_prefix}{basis_drop*100:.1f} ct</span>
            </div>
            <div class="rechenweg-zeile">
                <span>= Erwarteter Tages-Tiefstpreis</span>
                <span style="color:#008b8b; font-size:1.1rem;">{ki_ziel:.3f} €</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # --- NEU: PREIS-VERLAUF CHART ---
        chart_fig = erstelle_preis_chart(sheet_daten, ort_in, srt_in, ki_ziel)
        if chart_fig:
            st.plotly_chart(chart_fig, use_container_width=True)

        # --- ERFOLGSQUOTE ---
        quote, q_msg = berechne_erfolgsquote(sheet_daten, srt_in)
        with st.expander("📊 Wie treffsicher ist die KI?"):
            if quote is not None:
                farbe = "#28a745" if quote >= 60 else "#ffc107" if quote >= 40 else "#dc3545"
                st.markdown(f"<h2 style='color:{farbe}; margin:0;'>{quote}%</h2>", unsafe_allow_html=True)
                st.write(f"Vorhersage war in **{q_msg}** Fällen korrekt.")
                st.progress(quote / 100)
            else:
                st.info(f"ℹ️ {q_msg}")
            st.caption("Treffsicherheit steigt mit mehr gesammelten Daten (Ziel: 4+ Wochen).")

        # --- PREIS-TOTEM ---
        mast = '<div class="totem-mast">'
        farben = ["#28a745", "#ffc107", "#dc3545"]
        for i, s in enumerate(stationen[:3]):
            c = farben[i]
            dist_str = f"{s.get('dist', '?')} km"
            mast += (
                f'<div class="mast-row">'
                f'<div><b style="font-size:1rem;">{s["brand"]}</b><br>'
                f'<small style="color:#888;">{dist_str}</small></div>'
                f'<div style="color:{c}; font-size:1.7rem; font-weight:900;">{s["price"]:.3f}</div>'
                f'</div>'
            )
        st.markdown(mast + '</div>', unsafe_allow_html=True)


# --- FOOTER ---
st.write("---")
with st.expander("🛡️ System-Status"):
    col_a, col_b = st.columns(2)
    with col_a:
        if hole_gcp_creds():
            st.success("✅ Google Sheets verbunden")
        else:
            st.error("❌ Google Sheets nicht verbunden")
    with col_b:
        oel = hole_marktpreis("BZ=F")
        if oel:
            st.metric("Brent Rohöl", f"{oel} $")
        else:
            st.warning("Ölpreis nicht verfügbar")
