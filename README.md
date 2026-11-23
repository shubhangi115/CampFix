# CampFix

A campus complaint management website where students report issues and track their status, and administrators review and resolve complaints.

## Demo

> Run CampFix locally, then open [the website](http://localhost:8501)

## Features

- Student registration and sign-in
- Separate administrator sign-in and dashboard
- Complaint submission, search, and filters
- Editing and deletion of pending complaints
- Status tracking from **Pending** to **In Progress** to **Resolved**
- Resolution notes and administrator status history
- JWT authentication and Argon2 password hashing

## Tech Stack

- Python
- FastAPI
- Streamlit
- MySQL

## Run Locally

Install Python 3.12 and MySQL Server 8.0.40 or 8.4. Run the PowerShell commands below from the CampFix folder unless a step specifies the MySQL prompt.

### Clone the repository

Replace `YOUR-USERNAME` with your GitHub username. `git clone` downloads the repository, and `cd` opens its folder in the terminal.

```powershell
git clone https://github.com/YOUR-USERNAME/CampFix.git
cd CampFix
```

### Install dependencies

Create a virtual environment to keep CampFix’s packages separate, then install the packages listed in `requirements.txt`.

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Set up MySQL

Open the MySQL command-line client as root from the project folder. At the `mysql>` prompt, run the following commands. `SOURCE` creates the database and tables. `CREATE USER` creates CampFix’s database account, and `GRANT` gives it permission to read and update records.

```sql
SOURCE database/schema.sql
CREATE USER 'campfix_app'@'127.0.0.1' IDENTIFIED BY 'your-database-password';
GRANT SELECT, INSERT, UPDATE ON campfix_db.* TO 'campfix_app'@'127.0.0.1';
```

### Configure environment variables

Create a `.env` file in the project folder using `.env.example` as a template. Use the same database password you chose in MySQL. Keep `.env` out of Git.

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=campfix_app
DB_PASSWORD=your-database-password
DB_NAME=campfix_db
JWT_SECRET=replace-with-a-generated-secret
JWT_MINUTES=60
API_BASE_URL=http://127.0.0.1:8000
```

Run this command to generate a random secret. Paste the output into `.env` as `JWT_SECRET`. FastAPI uses it to sign and verify login tokens.

```powershell
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

### Create an administrator

This script prompts for the email and password you’ll use on the CampFix **Admin sign-in** screen.

```powershell
.\venv\Scripts\python.exe -m scripts.create_admin
```

### Start the backend

Uvicorn starts FastAPI on port `8000`. Leave this terminal running.

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app
```

### Start the frontend

In a second terminal, start Streamlit. It displays the website and sends requests to FastAPI.

```powershell
.\venv\Scripts\python.exe -m streamlit run frontend/app.py
```

Open [CampFix](http://localhost:8501) in your browser.
