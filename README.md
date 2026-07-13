# Customer Lookup Tool

Search for a customer by phone number across all your scattered Google Sheets,
and see exactly which sheet + tab + row their data lives in.

## How it works
- You list your Google Sheet links once in `sheets_config.csv`.
- The app connects to Google Sheets using a "service account" (a robot Google
  account you create for free — no OAuth login flow, no per-user setup).
- Every tab of every listed sheet gets scanned. Phone numbers are auto-detected
  (by column header like "Phone"/"Mobile"/"Contact Number", or by pattern if
  no header matches) and indexed.
- You search a phone number in the app and get back every matching row, with
  full details and the source sheet/tab name.

## One-time setup (about 10 minutes)

### 1. Create a Google Cloud service account
1. Go to https://console.cloud.google.com/ and create a new project (or use an existing one).
2. Go to **APIs & Services → Library**, enable **Google Sheets API** and **Google Drive API**.
3. Go to **APIs & Services → Credentials → Create Credentials → Service Account**.
4. Give it any name (e.g. `customer-lookup-bot`). Skip optional role assignment.
5. Once created, open the service account, go to the **Keys** tab → **Add Key → Create new key → JSON**.
6. This downloads a `.json` file. Rename it to `credentials.json` and place it in this same folder.

### 2. Share your sheets with the service account
- Open `credentials.json`, find the field `"client_email"` — it looks like
  `customer-lookup-bot@your-project.iam.gserviceaccount.com`.
- For **every** Google Sheet you want searchable, click **Share** and add that
  email as a **Viewer**. (This is the only "per-sheet" step — takes a few
  seconds per sheet, and you only redo it when a brand-new sheet shows up.)

### 3. List your sheets
Open `sheets_config.csv` and replace the example rows with your real sheets:
```
friendly_name,sheet_url
D2C Orders - Jan,https://docs.google.com/spreadsheets/d/1AbCdEf.../edit
Franchise Leads,https://docs.google.com/spreadsheets/d/1XyZ123.../edit
```
Add one row per sheet. `friendly_name` is just a label so results are readable.

### 4. Install and run
```bash
pip install -r requirements.txt
streamlit run app.py
```
This opens the app in your browser at `http://localhost:8501`.

## Using the app
- Click **Refresh data** the first time (and whenever your sheets change) to pull the latest data.
- Type a phone number in any format — `9876543210`, `+91 98765 43210`, `98765-43210` — it's normalized automatically.
- Results show every match with the sheet name, tab name, row number, and the full row of data.

## Deploying so you don't need to run it locally
Easiest free option: **Streamlit Community Cloud** (share.streamlit.io):
1. Push this folder to a GitHub repo (⚠️ do NOT commit `credentials.json` — add it to `.gitignore`).
2. On Streamlit Cloud, create a new app pointing at the repo.
3. In the app's **Settings → Secrets**, paste the contents of your `credentials.json` (Streamlit secrets can hold it securely instead of committing the file).
4. Update `data_loader.py`'s `get_client()` to read from `st.secrets` instead of a local file when deployed (small tweak — ask me if you want this wired up).

## Notes / things worth knowing
- If a sheet has no column header containing "phone"/"mobile"/etc., the tool
  falls back to scanning every cell in a row for anything that looks like a
  phone number (10–13 digits). This catches oddly-named columns but can be
  slower on very large sheets.
- If two different customers share tabs across sheets with the same phone
  number (e.g. updated records), you'll see all matches listed — useful for
  spotting duplicates too.
- The service account only has **read** access — this tool can't accidentally
  edit your sheets.
