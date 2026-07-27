# Public Transport Delay Monitor & RAG Agent System

An enterprise process orchestration system for tracking, filtering, indexing, and analyzing Prague public transport delays using **Camunda 8**, **Python Zeebe Job Workers**, **ChromaDB Vector Store**, and **MCP AI Agents**.

This project processes real-time vehicle positions via the **Golemio API**, identifies delays ($\ge 10$ mins), filters out duplicate entries, exports structured logs, indexes semantic vectors into **ChromaDB**, and enables **RAG (Retrieval-Augmented Generation)** delay querying.

---

## 🏗️ System Architecture

   ┌───────────────────────────────┐
   │  AI Agent  Camunda LLM Task   │
   └─────────────┬─────────────────┘
                 │ JSON-RPC (MCP)
                 ▼
┌─────────────────────────────────────────────────────────┐
│     Golemio MCP Server (FastMCP)                        │
│       (agents/mcp_server.py)                            │
└───────────┬─────────────────┬───────────────────┬───────┘
            │                 │                   │   
            ▼                 ▼                   ▼   
 ┌──────────────────┐  ┌──────────────   ┌────────────────┐
 │  Local Dataset   │  │ Golemio REST │  │  Embed & Sync  │
 │ (data\*.json csv)│  │     API      │  │  to ChromaDB   │
 └──────────────────┘  └──────────────┘  └────────┬───────┘
                                                  │
                                                  ▼
                                         ┌────────────────┐
                                         │rag-delay-query │
                                         │  (AI Agent)    │
                                         └────────┬───────┘
                                                  │
												  ▼
                                         ┌────────────────┐
                                         │ Semantic Vector│
                                         │  RAG Response  │
                                         └────────────────┘




## Process diagrams for agents

                              ┌────────────────────────┐
                              │    Camunda 8 Engine    │
                              │ (Zeebe / c8run:26500)  │
                              └───────────┬────────────┘
                                          │
      ┌─────────────────┬─────────────────┼───────────────────┬─────────────────┐
      ▼                 ▼                 ▼                   ▼                 ▼
┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐
│ load-history │  │ fetch-golemio │  │   filter-    │  │  export-data  │  │index-chromadb│
│    Worker    │  │    -data      │  │  duplicates  │  │    Worker     │  │    Worker    │
└──────┬───────┘  └──────┬────────┘  └──────┬───────┘  └──────┬────────┘  └──────┬───────┘
       │                 │                  │                 │                  │
       ▼                 ▼                  ▼                 ▼                  ▼
┌──────────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────┐  ┌──────────────┐
│ Read history │  │ Golemio REST  │  │ Evaluate     │  │ Write JSON/CSV│  │ Embed & Sync │
│ JSON files   │  │ API           │  │ hasNewDelays │  │ to data/      │  │ to ChromaDB  │
└──────────────┘  └───────────────┘  └──────────────┘  └───────────────┘  └──────┬───────┘
                                                                                 │
                                                                                 ▼
                                                                        ┌────────────────┐
                                                                        │rag-delay-query │
                                                                        │  (AI Agent)    │
                                                                        └────────┬───────┘
                                                                                 │
                                                                                 ▼
                                                                        ┌────────────────┐
                                                                        │ Semantic Vector│
                                                                        │  RAG Response  │
                                                                        └────────────────┘
																		
## 📁 Directory Structure

..\AI\aJizdniVykony\delay\
│
├── .git/                          # Git repository
├── venv/                          # Python virtual environment
├── data/                          # Raw JSON/CSV exports
│   └── processed/                 # Archived JSON files after ChromaDB import
├── chroma_db/                     # Persistent ChromaDB vector database
│
├── golemioCsv.py                  # Standalone monolithic script
├── importFinal.py                 # Original standalone ChromaDB import script
├── delay-monitor-process.bpmn     # Camunda 8 BPMN process diagram
├── time-window-rules.dmn          # Camunda 8 DMN decision table
├── run_all_workers.py             # Multi-worker runner launcher
├── README.md                      # Documentation
│
├── workers/                       # Core Process Job Workers
│   ├── __init__.py
│   ├── worker_load_history.py     # Task: load-history
│   ├── worker_fetch_golemio.py    # Task: fetch-golemio-data
│   ├── worker_filter_duplicates.py# Task: filter-duplicates
│   └── worker_export_data.py      # Task: export-data
│
├── agents/                        # AI Agents & Vector Store Connectors
│   ├── __init__.py
│   ├── chroma_indexer_agent.py    # Agent/Worker: index-chromadb
│   ├── rag_query_agent.py         # Agent/Worker: rag-delay-query
│   ├── mcp_server.py              # Model Context Protocol (MCP) server
│   └── worker_agent_orchestrator.py # LLM Agent Orchestrator
│
└── utils/                         # Helper modules
    ├── __init__.py
    └── golemio_helpers.py         # Shared API and parsing utilities
	
## Business Process

1. Timer Start Event: "Trigger every 4 minutes"
    • Action: This event automatically instantiates the process without manual intervention. It replaces the infinite while True loop and time.sleep(240) logic from the original Python script. 
    • Camunda Configuration: Set the Timer Definition Type to Cycle and the ISO 8601 value to R/PT4M. 
2. Service Task: "Load Historical Run Data"
    • Action: A job worker reads the most recent JSON file from the local data directory to establish the baseline of previously recorded delays. This prevents the system from logging duplicate delays. 
    • Task Definition Type: load-history. 
    • Input Variables: None required to start.
    • Output Variables:
        ◦ max_old_time: The latest timestamp from the previous run. 
        ◦ last_records: A dictionary mapping existing vehicle delays (linka, obeh, vozidlo, den, prijezd) to their delay duration. 
3. Service Task: "Fetch Vehicle Positions from Golemio API"
    • Action: The process makes a GET request to [https://api.golemio.cz/v2/vehiclepositions](https://api.golemio.cz/v2/vehiclepositions) to fetch current bus locations. 
    • Task Definition Type: fetch-golemio-data. 
    • Input Variables:
        ◦ limit: Set to 10000 to download all vehicle positions for local filtering. 
        ◦ GOLEMIO_API_KLIC: The access token passed securely in the request header. 
    • Output Variables:
        ◦ rawVehicles: The raw JSON array extracted from the features property of the API response. 
4. Business Rule Task (DMN): "Determine Delay Category & Validity"
    • Action: The process evaluates rules to determine if a vehicle qualifies for processing based on its route number and delay duration. It also assigns a specific time window based on the arrival hour. 
    • Input Variables:
        ◦ routeNumber: The route number extracted from the data, which must be between 100 and 999. 
        ◦ delayMinutes: The actual delay, which must be $\ge$ 10 minutes. 
        ◦ arrivalHour: The extracted hour, used to map to categories like zpozdeni_06_09. 
    • Output Variables:
        ◦ isValid: Boolean confirming the vehicle meets the criteria. 
        ◦ timeWindow: The string representing the time category. 
5. Service Task: "Filter against Historical Duplicates"
    • Action: The worker compares the currently delayed buses against the historical records loaded in Step 2. A record is kept only if its current delay is strictly greater than the previously recorded delay. 
    • Task Definition Type: filter-duplicates. 
    • Input Variables:
        ◦ rawVehicles: The valid buses retrieved from the API. 
        ◦ last_records: The historical dictionary. 
        ◦ max_old_time: The timestamp cutoff. 
    • Output Variables:
        ◦ filteredVehicles: The final list of buses with new or increased delays. 
        ◦ hasNewDelays: A boolean flag that is true if filteredVehicles contains items. 
6. Exclusive Gateway (XOR): "Are there new delays to record?"
    • Action: The gateway evaluates the hasNewDelays variable to direct the process flow. 
    • Yes Branch:
        ◦ Condition: =hasNewDelays = true. 
        ◦ Routing: Directs the token forward to the "Export Data to JSON & CSV" task. 
    • No Branch:
        ◦ Condition: =hasNewDelays = false. 
        ◦ Routing: Directs the token to the "Cycle Skipped" End Event, bypassing export and database indexing entirely. 
7. Service Task: "Export Data to JSON & CSV"
    • Action: The worker receives the final payload, formats timestamps, and writes the data. It creates a new JSON file for the run and appends the records incrementally to a master CSV file. 
    • Task Definition Type: export-data. 
    • Input Variables:
        ◦ filteredVehicles: The validated delay data. 
    • Output Variables:
        ◦ exportStatus: Confirmation that files were successfully written to the data/ directory. 
8. Service Task: "Index Delays to ChromaDB Vector Store"
    • Action: The worker loads the newly exported JSON records, flattens their metadata, and utilizes a SentenceTransformer model to generate vector embeddings. It checks if records exist in ChromaDB and conditionally upserts them if the new delay is larger. Finally, it moves the processed JSON files to the data/processed archive directory. 
    • Task Definition Type: index-chromadb. 
    • Input Variables:
        ◦ Path references to the data/ directory where the JSON files reside. 
    • Output Variables:
        ◦ chromaIndexResult: A summary object detailing the count of new records, updated records, and skipped records. 
9. Service Task: "Query Delay Intelligence via RAG"
    • Action: The worker simulates a test cycle by extracting a line number and date from a natural language query. It connects to the delays collection in ChromaDB and performs a semantic search filtered by the extracted metadata (linka and den). 
    • Task Definition Type: rag-delay-query. 
    • Input Variables:
        ◦ searchQuery (e.g., "Jaké měla zpoždění linka 177 dne 4.3. ?"). 
    • Output Variables:
        ◦ ragQueryResult: Contains the found_docs (documents) and found_metas (metadata and root causes) resulting from the ChromaDB vector query. 
10. End Events
    • Data Exported & Indexed: If the "Yes" branch was taken, the process reaches this end event after the data is exported, embedded, and queried. 
    • Cycle Skipped: If the "No" branch was taken at the gateway, the process reaches this end event and finishes immediately. 

    └── golemio_helpers.py         # Shared API and parsing utilities

##  ⚙️ Setup & Prerequisites. 

	# 1. Environment & Dependencies
		Bash		cd /d D:\AI\aJizdniVykony\delay
				.\venv\Scripts\activate
				pip install pyzeebe requests chromadb sentence-transformers mcp
	# 2. Environment Variables
		DOS			set GOLEMIO_API_KLIC=your_golemio_api_token_here


##  🤖 Agent Specifications (agents/)
      Agent / Worker Script  
	  
	  Task Type (zeebe:taskDefinition)
	  
	  Worker Script:
	  Output Variables: 
	  
	# 1.Agent chroma_indexer_agent
	    Worker Script:		    pyindex-chromadb
		Input Variables:		None
		Output Variables:	  	chromaIndexResult
		Description:
			Reads pending JSON files, generates multilingual embeddings using SentenceTransformer, 
			upserts unique delay records into ChromaDB, and moves processed files to data/processed.
	  
	# 2.Agent rag_query_agent
	    Worker Script:		    pyrag-delay-query
		Input Variables:		searchQuery
		Output Variables:	  	ragQueryResult
	    Description:
			Parses route number and date from query, executes hybrid vector + metadata retrieval 
			on ChromaDB, and outputs structured RAG findings.
	
##  🚀 Running the Orchestration

# 1. Deploy Process & DMN:
    Open delay-monitor-process.bpmn in Camunda Desktop Modeler and click Deploy to localhost:26500.
# 2. Launch Workers & Agents:
	Bash		python run_all_workers.py
# 3. Monitor Execution:
	Check instance tokens and variable states in Camunda Operate (http://localhost:8081/operate).

##  🔌 Model Context Protocol (MCP) Integration

	The project includes an MCP server (agents/mcp_server.py) exposing the query_chromadb_rag tool. 
	This allows Claude Desktop, Cursor, or Camunda Trial LLM Connectors to query ChromaDB transport 
	vector embeddings directly.
	
	  MCP Tool Name:	query_chromadb_rag
	  Description:
						Performs semantic vector retrieval against ChromaDB for delay causes and details, 
						applying hybrid metadata filtering (linka, den).  
	  Inputs:			natural_query (String, e.g., "Jaké měla zpoždění linka 177 dne 4.3.?")
	  Output:			JSON payload containing vector-matched documents, exact metadata, delay durations, 
						and cause descriptions.  
##  Test log	
	(.venv) PS D:\AI\aJizdniVykony\delay> 
	& d:\AI\aJizdniVykony\delay\.venv\Scripts\python.exe 
	    d:/AI/aJizdniVykony/delay/golemioCsv.py
		Inicializuji hlavní CSV soubor: data\export_zpozdeni_20260728_001122.csv
		Spouštím nekonečnou smyčku dotazování. Pro ukončení stiskněte Ctrl+C.

		--- Spouštím dotaz v 00:11:22 ---
		Žádný dnešní předchozí záznam nenalezen. Bude se zpracovávat vše.
		Stahuji aktuální data z Golemio API...
		Zpracovávám 337 vozidel. Hledám zpoždění >= 10 min...
		ÚSPĚCH: Nalezeno a zapsáno 2 NOVÝCH/AKTUALIZOVANÝCH zpoždění autobusů.
		Data uložena do: data/20260728_001122.json a připsána do data\export_zpozdeni_20260728_001122.csv
		00:11 - Čekám 4.0 minuty na další dotaz...
		Skript byl ručně ukončen uživatelem.
		
		
