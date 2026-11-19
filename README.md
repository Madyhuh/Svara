# Svara starter

This is an integrated Flask frontend/backend scaffold. It has a working browser webcam preview and SQLite language API. It does NOT yet perform hand detection, sign recognition, translation, login, or learning streaks.

## Run in VS Code terminal (Windows)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 and then /recognize. If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -r requirements.txt` followed by `.venv\Scripts\python.exe app.py`.

The SQLite database is created on the first run. `/api/languages` returns the three configured language entries.

Run with debug=True only for local development. The browser camera requires permission and HTTPS outside localhost.
