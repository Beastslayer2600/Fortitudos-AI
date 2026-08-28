Failed to fetch on Learn = the browser never got a CORS-ok reply from :8000.

On the laptop:
1. Use http://localhost:8080 not Vercel.
2. Home backend = http://127.0.0.1:8000
3. Restart python app.py after app.py has do_OPTIONS.
4. In the same browser open http://127.0.0.1:8000/api/status — you must see JSON.
