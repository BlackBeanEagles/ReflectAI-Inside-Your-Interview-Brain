import sqlite3, os

db_path = os.path.expandvars(r'%LOCALAPPDATA%\Ollama\db.sqlite')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

for table in tables:
    print(f"\n--- {table} ---")
    cur.execute(f"SELECT * FROM {table}")
    for row in cur.fetchall():
        print(row)

conn.close()
