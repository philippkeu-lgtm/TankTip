import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import timesfm

def get_timesfm_prediction(historie):
    try:
        tfm = timesfm.TimesFm(
            context_len=24,
            horizon_len=1,
            input_patch_len=32,
            output_patch_len=128,
            backend='cpu'
        )
        tfm.load_from_checkpoint(repo_id="google/timesfm-1.0-200m")
        forecast_daten = tfm.forecast([historie])
        ki_preis = float(forecast_daten[0][0])
        return round(ki_preis, 3)
    except Exception as e:
        print(f"Fehler bei KI: {e}")
        return historie[-1] if historie else 0.0

def run_predictor():
    gcp_json = os.environ.get("GCP_SERVICE_ACCOUNT")
    if not gcp_json:
        print("Fehler: Keine Google Cloud Zugangsdaten!")
        return

    try:
        creds_dict = json.loads(gcp_json)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        sheet = client.open("Tankprotokoll").sheet1

        alle_daten = sheet.get_all_records()
        
        # Wir lassen die KI jetzt auf alle drei Sorten los!
        kraftstoffe = ['e5', 'e10', 'diesel']
        
        for sorte in kraftstoffe:
            sorten_daten = []
            zeilen_nummern = []
            aktuelle_zeile = 2 
            
            for row in alle_daten:
                if str(row.get('Sorte', '')).lower() == sorte:
                    try:
                        preis = float(str(row.get('Bestpreis', '')).replace(',', '.'))
                        sorten_daten.append(preis)
                        zeilen_nummern.append(aktuelle_zeile)
                    except ValueError:
                        pass 
                aktuelle_zeile += 1

            if not sorten_daten:
                print(f"Keine Daten für {sorte.upper()} gefunden.")
                continue

            historie_fuer_ki = sorten_daten[-24:]
            print(f"Berechne TimesFM Vorhersage für {sorte.upper()} ({len(historie_fuer_ki)} Punkte)...")
            
            ki_preis = get_timesfm_prediction(historie_fuer_ki)
            
            letzte_zeile = zeilen_nummern[-1]
            # Schreibe den KI Preis in Spalte E (5)
            sheet.update_cell(letzte_zeile, 5, ki_preis)
            print(f"Erfolg: {sorte.upper()}-Ziel ({ki_preis}€) in Zeile {letzte_zeile} eingetragen!")

    except Exception as e:
        print(f"Fehler im Predictor: {e}")

if __name__ == "__main__":
    run_predictor()
