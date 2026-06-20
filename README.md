# Abstract Finder

Abstract Finder is a robust, responsive web application designed to automatically resolve, fetch, and backfill missing or incomplete abstracts for scientific papers from your academic bibliography files. 

Developed collaboratively with **Antigravity** by **Mohit Kaushik**, this tool helps researchers, students, and systematic literature review (SLR) authors quickly enrich their paper databases.

---

## 🌟 Key Features

- **Multi-Format Support**: Upload bibliography files in `.bib` (BibTeX), `.csv` (comma-separated), or `.ris` (Research Information Systems) formats. Download your enriched databases back into `.bib`, `.csv`, or `.ris` formats on-the-fly.
- **Robust Parallel Fetching**: Resolves papers concurrently in the background using multi-threaded task managers without freezing or locking the server UI.
- **Multiple API Providers & Polite Pools**:
  - **OpenAlex** (No key required, polite pool auto-identified)
  - **Crossref** (No key required, polite pool auto-identified)
  - **CORE** (Requires a free API key)
  - **Semantic Scholar** (Allows keyless polite rate limits or official API key)
- **LaTeX Title Normalization**: Automatically strips LaTeX formatting, curly braces, mathematical notation (e.g., math-mode `$`), and formatting commands (e.g., `\textit{...}`) to clean paper titles before searching.
- **TLDR Summaries**: Extracts and showcases quick 1-sentence TLDR summaries beneath the full abstracts where available.
- **Privacy-First Architecture**: Your API keys and configuration settings are stored **locally in your browser's `localStorage`**. No personal keys or search parameters are tracked, logged, or sent to external intermediate servers.
- **Interactive UI**: Clean, high-performance dashboard styled with premium dark-themed vanilla CSS and smooth micro-animations. Contains a real-time progress bar, logs drawer, and interactive search configuration.

---

## 🚀 Getting Started (Windows Quick Start)

If you are on Windows, simply double-click the setup batch script in the root directory:

> [!TIP]
> **No Command Line Knowledge Needed**: The `start.bat` script is designed specifically for users who are not familiar with running terminal commands. Double-clicking this file handles the entire setup (creating the virtual environment, installing libraries, and initiating the server) automatically without requiring you to copy-paste or execute any manual commands.

1. Double-click the **`start.bat`** file.
2. The script will automatically:
   - Verify Python is installed.
   - Create a virtual environment (`venv`) if it does not exist.
   - Activate the virtual environment.
   - Install the project dependencies from `requirements.txt`.
   - Run database migrations (`python manage.py migrate`).
   - Start the Django development server.
3. Open your browser and navigate to: **`http://127.0.0.1:8000/`**

---

## 🔧 Manual Setup & Run (All OS)

If you prefer to run the commands manually or are on macOS/Linux:

### 1. Clone the Repository & Navigate to Folder
```bash
cd "Abstract Finder"
```

### 2. Create and Activate a Virtual Environment
- **Windows**:
  ```bash
  python -m venv venv
  call venv\Scripts\activate
  ```
- **macOS / Linux**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Apply Database Migrations
```bash
python manage.py migrate
```

### 5. Launch the Server
```bash
python manage.py runserver
```
Visit **`http://127.0.0.1:8000/`** in your browser.

---

## 🛡️ Privacy and API Keys

The app functions fully out-of-the-box using the public polite pools of OpenAlex and Crossref. To increase query speed and accuracy, you can supply optional API keys inside the **Configure APIs** drawer in the dashboard:

1. **Semantic Scholar API Key**: Allows faster rate limits. Get one from [Semantic Scholar Partner Access](https://www.semanticscholar.org/product/api).
2. **CORE API Key**: Recommended for resolving open-access conference preprints. Get a free key at [core.ac.uk/services/api](https://core.ac.uk/services/api).
3. **Polite Pool Email**: Crossref and OpenAlex request a valid contact email to place your requests in their polite pools (~10 requests/sec).

> [!IMPORTANT]
> **Data Security**: All keys are stored directly in your browser's local cache. The Django server acts as a proxy for the third-party endpoints to avoid CORS issues, meaning your credentials never persist on any database server.

---

## 🧪 Testing & Sample Files

The codebase includes comprehensive unit tests validating RIS parsing/serialization, LaTeX title normalization, parallel resolving mechanisms, and API proxy logic. 

To run the automated test suite:
```bash
python manage.py test
```

### 📁 Sample Input Files
Inside the [test/](file:///f:/Abstract%20Finder/test) folder, we have included three pre-configured sample files representing each supported input format:
1. **`OSS_ERA2_Pilot.csv`**: A Publish or Perish formatted CSV dataset containing metadata and partial citation fields.
2. **`OSS_ERA2_Pilot.ris`**: A Research Information Systems (RIS) bibliographic dataset.
3. **`pop_results.bibtex`**: A BibTeX citation reference library.

These sample files are provided to help users understand the input requirements and easily get familiar with the tool's abstract resolution pipeline. You can upload any of these files directly via the dashboard homepage to test the tool out-of-the-box.

---

## 📁 Repository Structure

```
Abstract Finder/
├── abstract_finder/      # Django project settings
├── finder/               # Main application app
│   ├── static/           # CSS styles & client-side JavaScript
│   ├── templates/        # Dashboard HTML templates
│   ├── abstract_fetcher.py # Normalization and API fetch routines
│   ├── task_manager.py   # Multi-threaded background queue processor
│   ├── tests.py          # Django automated unit tests
│   └── views.py          # Endpoint controllers (upload, download, proxy)
├── test/                 # Sample input files (.bib, .ris, .csv) for testing
├── requirements.txt      # Project requirements list
├── start.bat             # Auto-setup and launcher utility
├── fetching_abstract.py  # Standalone Colab/CLI script
├── LICENSE              # MIT License terms
└── README.md             # Project documentation
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](file:///f:/Abstract%20Finder/LICENSE) file for details.
