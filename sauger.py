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
    
    # NEU: Wir nutzen die "all"-Abfrage, um E5, E10 und Diesel gleichzeitig zu bekommen
    # Koordinaten für Schleswig (Flensburger Str.)
    url = f"https://creativecommons.tankerkoenig.de/json/list.php?lat=54.526&lng=9.546&rad=4&sort=dist&type=all&apikey={tk_key}"
    
    try:
        # Sheet verbinden
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1

        print("Frage Tankerkönig ab...")
        response = requests.get(url)
        data = response.json()
        
        if data.get("ok") and len(data.get("stations", [])) > 0:
            # Wir suchen gezielt nach "WIKING", wenn nicht gefunden, nehmen wir die nächstbeste
            ziel_station = None
            for station in data["stations"]:
                if "WIKING" in station.get("name", "").upper():
                    ziel_station = station
                    break
            
            # Falls WIKING nicht in der Liste ist, nehmen wir die erste Station
            if not ziel_station:
                ziel_station = data["stations"][0]
                print(f"WIKING nicht gefunden, nutze Alternative: {ziel_station.get('name')}")
            
            station_name = ziel_station.get("name")
            
            # Preise auslesen (kann None sein, wenn die Sorte nicht angeboten wird)
            preise = {
                "e5": ziel_station.get("e5"),
                "e10": ziel_station.get("e10"),
                "diesel": ziel_station.get("diesel")
            }
            
            # Für jede Sorte eine eigene Zeile anlegen
            for sorte, preis in preise.items():
                if preis: # Nur eintragen, wenn es auch einen Preis gibt
                    zeile = [zeit_jetzt, "24837", sorte, preis, "", "", "🤖 Auto-Sauger", station_name]
                    sheet.append_row(zeile)
                    print(f"Erfolg: {sorte.upper()} für {preis}€ bei {station_name} eingetragen.")
        else:
            print("Fehler: Keine Stationen gefunden oder API-Limit erreicht.")

    except Exception as e:
        print(f"Fehler beim Ausführen: {e}")

if __name__ == "__main__":
    run_sauger()
