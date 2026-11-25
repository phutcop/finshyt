# finshyt

A local financial expense analysis demo with a React frontend and FastAPI backend. It accepts one annual expense CSV or spreadsheet at a time, compares spending across months, and answers questions using recorded ledger data.

## Run locally

From this directory:

```bash
python3 start_local.py
```

Open [http://127.0.0.1:5174/](http://127.0.0.1:5174/). The API is at [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs). The launcher starts both services in the background, reuses healthy services, and saves logs and process IDs in `.local-run/`.

The current machine has `frontend/node_modules` and `backend/.venv` installed. On a fresh machine, install dependencies first:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd ../frontend
npm install
cd ..
python3 start_local.py
```

## Demonstrate the workflow

1. Open **Upload your ledger**.
2. Choose a CSV from `demo_files/`. Each file covers one calendar year and all 12 months, with 50,000 expenses.
3. Review the validation preview and select **Confirm import**.
4. Open **Dashboard**. The uploaded year is the active dataset. Compare monthly totals, category and department spending, and download the monthly comparison CSV.
5. Open **Chatbot** and ask, for example, "What changed from February to March 2026?" or "What if we cut Software Subscriptions by 20%?"

Uploads accept CSV, XLSX, and XLS. Expense files need date, amount, and description columns. Common alternative headers are mapped automatically. Preview reports invalid and duplicate rows within the file before confirmation. A confirmed annual file replaces the active expense ledger in `data2/expenses.csv`. Dashboard and advisor results then use only that file and compare its months. A file must contain expenses from only one calendar year.

## Architecture

- `frontend/`: React and Vite interface, dashboard, upload flow, and advisor.
- `backend/`: FastAPI endpoints, import validation, aggregates, warnings, and grounded question answering.
- `data2/`: confirmed CSV ledger and budgets used by the local demo.
- `demo_files/`: three annual CSV files for upload demonstrations.
- `start_local.py`: background launcher for ports 5174 and 8001.

## Public demo deployment

The frontend is built for GitHub Pages at `https://phutcop.github.io/finshyt/`. The Python API runs as a separate Render web service because GitHub Pages only hosts static files. The frontend uses `VITE_API_BASE_URL` at build time to contact the API. Set the GitHub repository variable `VITE_API_BASE_URL` to the Render service URL to enable the Pages deployment workflow.

The `render.yaml` Blueprint defines a free FastAPI service. Connect this repository in Render as a Blueprint, then copy its public URL into the GitHub repository variable. The Pages workflow builds on every push to `main` after that variable is set.

The hosted demo uses browser-specific temporary ledgers. Public demo uploads are limited to 10 MB and are lost when the free Render service restarts or sleeps. Use the included synthetic files for public demonstrations, not private financial data. The local launcher and local dataset still work without Render.

The advisor answers spending totals, month comparisons, named department and category combinations, top groups, transaction counts, monthly averages, spending shares, budget questions when a matching budget exists, and percentage scenarios from local records. An optional `GROQ_API_KEY` in `backend/.env` enables model phrasing for other questions. Supported calculations work without a key. Revenue and profit are outside the expense ledger, so the advisor does not invent them.

This is a local single-company demo. The login page is illustrative; it does not provide production authentication. The CSV storage is also a demo adapter, not a production database.
