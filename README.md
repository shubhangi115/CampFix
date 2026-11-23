# CampFix

CampFix is a campus complaint management website. Students report campus issues and follow their progress. Administrators review reports, update statuses, add resolution notes, and look up registered students.

## Architecture

Streamlit renders the website and sends HTTP requests to FastAPI. FastAPI validates JSON, checks the user's role, and talks to MySQL using MySQL Connector/Python and parameterized SQL.

```text
Browser → Streamlit → FastAPI → MySQL
           Web UI     REST API   Records
```

## Windows setup

Install Python 3.12 and MySQL Community Server 8.4. Keep the MySQL service running and have the root password ready. Open PowerShell in the extracted `CampFix` folder for the following steps.

### 1. Install Python dependencies

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Using the virtual environment's Python directly avoids changing PowerShell's script execution policy.

### 2. Create the database

Open the classic MySQL command-line client from PowerShell. If `mysql.exe` is on your PATH, you can use `mysql -u root -p` instead.

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe" -u root -p
```

At the `mysql>` prompt, run the following. Substitute a strong password of your own and keep it for the next step. If you opened the MySQL client from another directory, give `SOURCE` the full schema path with forward slashes, or start the client from the project folder.

```sql
SOURCE database/schema.sql
CREATE USER 'campfix_app'@'127.0.0.1' IDENTIFIED BY 'replace-this-password';
GRANT SELECT, INSERT, UPDATE ON campfix_db.* TO 'campfix_app'@'127.0.0.1';
EXIT;
```

### 3. Configure CampFix and create an admin

Generate a signing secret in PowerShell.

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
notepad .env
```

Set `DB_PASSWORD` to the MySQL app user's password and `JWT_SECRET` to the generated value. The example uses port 3306 and binds the API URL to the local computer. Adjust `DB_PORT` if your MySQL setup uses another port. Keep `.env` private.

```powershell
.\.venv\Scripts\python.exe -m scripts.create_admin
```

The script prompts for the administrator's email and password. Students create their accounts through the website.

### 4. Start FastAPI and Streamlit

In the first PowerShell window, from the project folder:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

In a second PowerShell window, also from the project folder:

```powershell
.\.venv\Scripts\python.exe -m streamlit run frontend/app.py --server.address 127.0.0.1
```

Open [CampFix](http://127.0.0.1:8501) or [Swagger UI](http://127.0.0.1:8000/docs). Use **Admin sign-in** on the CampFix access screen for the account created by the script.

### Troubleshooting

- **Streamlit cannot reach the API**. Check that the FastAPI terminal is running and that `API_BASE_URL` matches it.
- **Database operation failed**. Check the MySQL service, database schema, and app user's host, credentials, and privileges.
- **FastAPI will not start**. Set a random `JWT_SECRET` with at least 32 characters and restart.

## Endpoints

| Method and path | Purpose |
| --- | --- |
| `POST /auth/student/register` | Register a student. MySQL unique keys guard against duplicate emails and roll numbers. |
| `POST /auth/student/login`, `POST /auth/admin/login` | Verify the password with Argon2 and issue a signed JWT. |
| `GET /auth/me`, `POST /auth/logout` | Return the current profile or revoke the active session. |
| `POST /complaints`, `GET /complaints` | Create a pending complaint or list the student's complaints. Search and filter with `search`, `status`, and `category`. |
| `GET /complaints/{complaint_id}`, `PUT /complaints/{complaint_id}`, `DELETE /complaints/{complaint_id}` | Read, edit, or soft-delete an owned complaint. Edits and deletions require Pending status. |
| `GET /dashboard/stats`, `GET /dashboard/recent-complaints` | Read student counts and the five most recent reports. |
| `GET /admin/dashboard` | Read campus-wide counts, recent reports, and category totals. |
| `GET /admin/complaints`, `GET /admin/complaints/{complaint_id}` | List or inspect complaints and their associated student details. |
| `PATCH /admin/complaints/{complaint_id}/status` | Move a complaint to its next status. |
| `GET /admin/students` | Find students by name or roll number and see their complaint counts. |

Use the numeric `complaint_id` in URL paths. The corresponding display reference is available for search.

## Test with Swagger UI

1. Open `http://127.0.0.1:8000/docs`. Expand **POST /auth/student/register**, select **Try it out**, and send JSON containing `full_name`, `roll_number`, `department`, `email`, `password`, and `confirm_password`. Expect **201**, or **409** for a duplicate.
2. Use **POST /auth/student/login** with that email and password. Copy `access_token` from the **200** response. Click **Authorize**, paste the token without the `Bearer ` prefix, and confirm.
3. Use **POST /complaints** with `title`, `category`, `description`, and `location`. Try `Cleanliness` as the category. Expect **201** with status **Pending**, a numeric `complaint_id`, and a `reference` such as `CMP-0001`.
4. Use **GET /complaints** to list reports and filter by reference, status, or category. Try **GET** and **PUT /complaints/{complaint_id}** with the numeric ID. To test deletion, create a second pending complaint and delete it. Expect **204** and then **404** when fetching that ID.
5. Try an admin endpoint while authorized as a student and expect **403**. Use **POST /auth/admin/login** with the administrator's credentials, then replace the token through **Authorize**.
6. Use **PATCH /admin/complaints/{complaint_id}/status** on the first report with `{"status":"In Progress"}`. Then send `{"status":"Resolved","resolution_note":"The floor was cleaned."}`. Expect **200** each time. The admin detail endpoint shows both history entries. Signing back in as the student shows the resolution note.
7. Use **POST /auth/logout** with a valid token. Expect **204**. A subsequent protected request using the same token returns **401**.

The optional integration test creates records. Run it against a disposable MySQL database with the app and an admin already set up.

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
$env:CAMPFIX_TEST_URL = "http://127.0.0.1:8000"
$env:CAMPFIX_TEST_ADMIN_EMAIL = "your-test-admin@example.com"
$env:CAMPFIX_TEST_ADMIN_PASSWORD = "your-test-admin-password"
.\.venv\Scripts\python.exe -m pytest -q
```

## Code walkthrough

- **`frontend/app.py`** renders the access form and dispatches to the selected page. **`frontend/api_client.py`** calls FastAPI with the token from server-side Streamlit session state.
- **`backend/auth.py`** verifies Argon2 hashes and signs JWTs with an expiration. Each account has one active session ID in MySQL. FastAPI compares that ID with the JWT on every protected request. A new login replaces the old session and logout clears the matching ID in the database.
- **`backend/database.py`** opens a connection and provides a dictionary cursor. Successful operations commit and exceptions trigger rollback. SQL values go through connector parameters.
- **`backend/routes/complaints.py`** scopes student queries by student ID. MySQL generates the unique numeric key. The API then formats it as a readable reference with at least four digits. Soft deletion sets `deleted_at`, and normal lists and dashboards omit those rows.
- **`backend/routes/admin.py`** joins reports to student records and enforces **Pending → In Progress → Resolved**. Status changes and history inserts share a transaction. Student edits, student deletions, and admin updates lock the same complaint row, so an edit cannot pass the Pending check after a status change commits.
- **`database/schema.sql`** defines the four InnoDB tables, unique keys, and foreign keys. The status and category aggregates use `GROUP BY`. The student directory uses a `LEFT JOIN` to include students with zero active complaints.

Profiles are read-only. For public hosting, serve Streamlit over HTTPS and keep MySQL and the backend on a private service network. If the API is publicly exposed, serve it over HTTPS. The local development services bind to loopback.
