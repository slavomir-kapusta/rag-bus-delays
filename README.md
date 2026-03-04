
========================================

Bus Delays in Prague public city traffic - in Czech

========================================


EMBEDDING MODEL:  paraphrase-multilingual-MiniLM-L12-v2

chromaStats.py

		  STATISTIKA CHROMADB EMBEDDINGS
BertModel LOAD REPORT from: C:\AI\models\paraphrase-multilingual-MiniLM-L12-v2

Notes:
- UNEXPECTED    :can be ignored when loading from different task/architecture; not ok if you expect identical arch.

[1] POČET ZÁZNAMŮ
    Celkem vektorů v DB:  127

[2] VLASTNOSTI VEKTORŮ (EMBEDDINGS)
    Dimenze modelu:       384 čísel na jeden vektor
    Velikost 1 vektoru:   1536 bytů (raw float32)
    Teoretická RAM data:  190.50 KB (pouze vektory)

[3] VELIKOST NA DISKU
    Složka 'chroma_db':   1.20 MB
    (Obsahuje: indexy, metadata, texty a režii DB)

[4] ANALÝZA QUERY (Hledání)
    Dotaz:                'zpoždění autobusů'
    Doba vyhledávání:     0.0810 sekund
    Nejlepší shoda (dist):0.4402
    Počet vrácených:      10

===========================================================
# Golemio Incremental Bus Delay Fetcher (`golemioIncr.py`)

A Python script designed to incrementally fetch real-time public transit data from the [Golemio API](https://golemio.cz/) 
(Prague Integrated Transport). It specifically monitors bus lines (numbered 100-999), filters for vehicles delayed by 10 minutes or more, 
and exports the data into a JSON format optimized for vector databases like **ChromaDB**.


==================================================

SOURCE FILE ---   DELAY JSON: 

[
  {
    "id": "20260303_172256_L182",
    "document": "Dne 03.03.2026 měla linka 182 6 zpoždění 11 minut u zastávky U677Z1P (směr Opatov). Příčina: --- ",
    "metadata": {
      "den": "03.03.2026",
      "linka": 182,
      "zpozdeni": 11,
      "zastavka": "U677Z1P",
      "lat": 50.05718,
      "lon": 14.53642,
      "smer": "Opatov",
      "kategorie": "provoz",
      "pricina": "--- ",
      "prijezd": "17:12:00",
      "zpozdeni_00_06": 0,
      "zpozdeni_06_09": 0,
      "zpozdeni_09_12": 0,
      "zpozdeni_12_15": 0,
      "zpozdeni_15_18": 11,
      "zpozdeni_18_24": 0,
      "query": "Vytvoř seznam všech autobusových linek, které měly zpoždění delší než 10 minut dne 03.03.2026?",
      "timestamp": "20260303_172256"
    }
  },

CHROMA DB

[1] POČET ZÁZNAMŮ
    Celkem vektorů v DB:  11

[2] VLASTNOSTI VEKTORŮ (EMBEDDINGS)
    Dimenze modelu:       384 čísel na jeden vektor
    Velikost 1 vektoru:   1536 bytů (raw float32)
    Teoretická RAM data:  16.50 KB (pouze vektory)

[3] VELIKOST NA DISKU
    Složka 'chroma_db':   3.98 MB
    (Obsahuje: indexy, metadata, texty a režii DB)

[4] ANALÝZA QUERY (Hledání)
    Dotaz:                'zpoždění autobusů'
    Doba vyhledávání:     0.0714 sekundgolemioIncr
    Nejlepší shoda (dist):0.4453
    Počet vrácených:      10

RETRIEVE

golemioIncr.py


PROMPT TEMPLATES

>>> DOTAZ: 'Jaké měla zpoždění linka 348 dne 15.2. ?'
✅ NALEZENO 1 záznamů:
   [1] Dne 15.02.2026 měla příměstská linka 348 zpoždění 15 minut v 08:00 u zastávky Ládví (směr Ládví). Příčina: Kluzká vozovka na příjezdu do Prahy (D8).
       Příčina: Kluzká vozovka na příjezdu do Prahy (D8)

>>> DOTAZ: 'Měla linka 125 zpoždění 16.2. ?'
✅ NALEZENO 1 záznamů:
   [1] Dne 16.02.2026 měla linka 125 zpoždění 22 minut v 08:17 u zastávky Lihovar (směr Smíchovské nádraží). Příčina: Kolaps na Barrandovském mostě (ranní špička).
       Příčina: Kolaps na Barrandovském mostě

>>> DOTAZ: 'Zpoždění linky 911 dne 15.2. ?'
✅ NALEZENO 1 záznamů:
   [1] Dne 15.02.2026 měla noční linka 911 zpoždění 11 minut v 02:21 u zastávky Ve Žlíbku (směr Nádraží Hostivař). Příčina: Neošetřená vozovka (námraza).
       Příčina: Neošetřená vozovka (námraza) v nočních hodinách

>>> DOTAZ: 'Jaké měla zpoždění linka 348 dne 11.2. ?'
Nenalezeny zpoždění linky 348 pro den 11.02.2026
❌ NENALEZENO.

>>> DOTAZ: 'Zpoždění linky 128 dne 15.2.'
Nenalezeny zpoždění linky 128 pro den 15.02.2026
❌ NENALEZENO.


# Golemio Incremental Bus Delay Fetcher (`golemioIncr.py`)

A Python script designed to incrementally fetch real-time public transit data from the [Golemio API](https://golemio.cz/) 
(Prague Integrated Transport). It specifically monitors bus lines (numbered 100-999), filters for vehicles delayed by 10 minutes or more, 
and exports the data into a JSON format optimized for vector databases like **ChromaDB**.
---------------------

## 🚀 Key Features
* **Incremental Updates:** 
	Reads the last generated JSON file for the current day to ensure no duplicate records are created unless the bus delay has *increased*.
* **ChromaDB Ready:** 
	Formats the output with an `id`, `document` text, and rich `metadata` for easy vector embeddings and LLM querying.
* **Time-Window Categorization:** 
	Automatically bins delays into specific times of day (e.g., morning rush hour, afternoon, evening) for easier analytical querying.
* **Corporate Firewall Bypass:** 
	Includes SSL verification bypass to allow the script to run smoothly in environments with strict corporate proxies or custom certificates.
---
## 📋 Prerequisites
1. **Python 3.7+**
2. **Required Libraries:**
   ```bash
   pip install requests urllib3
---------------------
Setup & Configuration
---------------------
Set your API Key as an environment variable. The script requires the key to be stored in the GOLEMIO_API_KLIC variable.
On Windows (Command Prompt):	DOS		set GOLEMIO_API_KLIC=your_api_key_here
On Linux/macOS:

export GOLEMIO_API_KLIC="your_api_key_here"
Adjust the Minimum Delay (Optional):
By default, the script only logs buses delayed by 10 minutes or more. You can change this by modifying the MIN_DELAY constant at the top of the script:

Python
MIN_DELAY = 10 # Change to your preferred threshold in minutes
💻 Usage
Run the script from your terminal:

Bash
python goleioIncr.py
What happens when you run it?
The script checks for a local data/ directory (and creates it if it doesn't exist).

It looks for the most recent JSON file created today to load historical data.
It fetches up to 10,000 active vehicle positions from the Golemio API.
It filters the data to find buses (lines 100-999) with a delay >= MIN_DELAY.
It compares the newly fetched delays against the historical data. It will only record a vehicle if it hasn't been logged today, or if its delay has worsened.
If new data is found, it saves a new JSON file in the data/ folder named by the maximum arrival time found in the dataset (e.g., data/20231024_143000.json).

🗂️ Output Data Structure
The generated JSON files contain an array of objects structured specifically for RAG (Retrieval-Augmented Generation) applications.

Example Record:
JSON
[
  {
    "id": "20260303_172256_L182",
    "document": "Dne 03.03.2026 měla linka 182 6 zpoždění 11 minut u zastávky U677Z1P (směr Opatov). Příčina: --- ",
    "metadata": {
      "den": "03.03.2026",
      "linka": 182,
      "zpozdeni": 11,
      "zastavka": "U677Z1P",
      "lat": 50.05718,
      "lon": 14.53642,
      "smer": "Opatov",
      "kategorie": "provoz",
      "pricina": "--- ",
      "prijezd": "17:12:00",
      "zpozdeni_00_06": 0,
      "zpozdeni_06_09": 0,
      "zpozdeni_09_12": 0,
      "zpozdeni_12_15": 0,
      "zpozdeni_15_18": 11,
      "zpozdeni_18_24": 0,
      "query": "Vytvoř seznam všech autobusových linek, které měly zpoždění delší než 10 minut dne 03.03.2026?",
      "timestamp": "20260303_172256"
    }
  },
⚠️ Important Notes
SSL Warnings: Because verify=False is used in the requests.get() call and InsecureRequestWarning is disabled, ensure you understand the security implications if running outside a protected corporate network.

Cron/Automation: This script is designed to be run periodically (e.g., every 5-10 minutes via cron job or Windows Task Scheduler) to build a continuous dataset throughout the day.
===========================================================
