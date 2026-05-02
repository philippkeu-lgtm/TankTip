import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

def run_sauger():
    tz = pytz.timezone('Europe/Berlin')
    zeit_jetzt = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    
    tk_key = os.environ.get("TANKERKOENIG_API_KEY")
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    
    # Wir weiten den Radius leicht aus und fragen ALLE Sorten ab
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat=54.521&lng=9.551&rad=5&sort=dist&type=all&apikey={tk_key}"
    
    try:
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1

        print(f"--- Starte Diagnose-Lauf um {zeit_jetzt} ---")
        response = requests.get(url)
        data = response.json()
        
        if data.get("ok"):
            stations = data.get("stations", [])
            wiking_gefunden = False
            
            for s in stations:
                name = s.get("name", "").upper()
                if "WIKING" in name:
                    wiking_gefunden = True
                    # Wir loggen ALLES, was die API über WIKING sagt, in die GitHub Actions Konsole
                    print(f"Station gefunden: {s.get('name')}")
                    print(f"Preise in API -> E5: {s.get('e5')}, E10: {s.get('e10')}, Diesel: {s.get('diesel')}")
                    
                    preise = {
                        "e5": s.get("e5"),
                        "e10": s.get("e10"),
                        "diesel": s.get("diesel")
                    }
                    
                    for sorte, preis in preise.items():
                        # Wir tragen ALLES ein, was eine Zahl ist und über 0 liegt
                        if preis and preis > 0:
                            zeile = [zeit_jetzt, "24837", sorte, preis, "", "", "🤖 Auto-Sauger", s.get('name')]
                            sheet.append_row(zeile)
                            print(f"Eintrag erfolgreich: {sorte} = {preis}")
                        else:
                            print(f"Info: Kein Preis für {sorte} in der API gefunden.")
            
            if not wiking_gefunden:
                print("KEINE WIKING-STATION GEFUNDEN! Prüfe Koordinaten.")
        else:
            print(f"API-Fehler: {data.get('message')}")

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run_sauger()
