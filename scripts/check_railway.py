import mysql.connector
conn = mysql.connector.connect(
    host='thomas.proxy.rlwy.net', port=51505,
    user='root', password='fMYzIpahogVvRVHCACmBTOBQMzAEZevy',
    database='railway', charset='utf8mb4'
)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='railway'")
print('Tablas:', cur.fetchone()[0])
cur.execute("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='railway'")
print('Procedures:', cur.fetchone()[0])
conn.close()
