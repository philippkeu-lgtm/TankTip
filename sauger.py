import os
import json
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

def run_sauger():
    # Deutsche Zeit
    tz = pytz.timezone('Europe/Berlin')
    zeit_jetzt = datetime.now(tz).strftime("%d.%m.%Y %H:%M")
    
    tk_key = os.environ.get("TANKERKOENIG_API_KEY")
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat=54.516&lng=9.565&rad=5&sort=price&type=e5&apikey={tk_key}"
    
    try:
        # Sheet verbinden
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1

        response = requests.get(url)
        data = response.json()
        
        final_preis = None
        station_name = "WIKING Schleswig"

        if data.get("ok") and len(data.get("stations", [])) > 0:
            station_data = data["stations"][0]
            final_preis = station_data.get("price")
            if station_data.get("name"):
                station_name = station_data.get("name")

        # DER RETTUNGS-ANKER: Wenn Preis leer (None) oder 0 ist
        if not final_preis or final_preis == 0:
            print("Kein aktueller Preis. Suche letzten gültigen Wert...")
            all_values = sheet.get_all_values()
            
            letzter_preis = "Warten..."
            for row in reversed(all_values):
                # Wir suchen in Spalte D (Index 3) nach der letzten echten Zahl
                if len(row) >= 4 and row[3] not in ["", "Bestpreis", "Warten...", "None", None]:
                    letzter_preis = row[3]
                    break
            
            final_preis = letzter_preis

        # Eintragen
        zeile = [zeit_jetzt, "24837", "e5", final_preis, "", "", "🤖 Auto-Sauger", station_name]
        sheet.append_row(zeile)
        print(f"Erfolg: Preis {final_preis} eingetragen.")

    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run_sauger()
