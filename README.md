# ☀️ Job Creator

ECC Solar's internal tool: build client profiles, create job profiles under
each client, and automatically pull up the right resources (links, phone
numbers, docs) based on the job's fields.

**Proprietary software — see [LICENSE](LICENSE). Do not distribute.**

## How to run it (every time)

1. Open a terminal in this folder.
2. First time only, install the one dependency:

   ```
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```
   python app.py
   ```

4. Open your browser to **http://localhost:5000**

To stop the app, press `Ctrl+C` in the terminal.

Your data lives in `job_creator.db` (created automatically on first run).
Delete that file to start over with a fresh database.

## Build progress

- [x] **Piece 1** — Flask + SQLite skeleton; home page lists clients
- [x] **Piece 2** — “New client” form and client profile pages
- [x] **Piece 3** — Job profiles stored under each client
- [x] **Piece 4** — Rules engine: job selections → licenses, permits, compliance items (editable at /rules); service tickets with pre-fill; exportable job report
- [x] **Piece 5** — Edit jobs with version history for recordkeeping
- [ ] **Piece 6** — Polish (search, statuses, logins)
