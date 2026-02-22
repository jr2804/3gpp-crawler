import sqlite3

conn = sqlite3.connect('scripts/cache/tdoc_crawler.db')
print(conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall())
