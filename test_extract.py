import pyodbc
import sys
sys.path.append('.')
import pbi_parser

conn_str = 'Driver={ODBC Driver 18 for SQL Server};Server=biportal;Database=Raportal;Trusted_Connection=yes;TrustServerCertificate=Yes'
try:
    conn = pyodbc.connect(conn_str, timeout=10)
    query = """
    SELECT TOP 1 ItemID, Name, Content 
    FROM dbo.Catalog 
    WHERE Type = 13 
      AND Path NOT LIKE '%Silinen Raporlar%' 
      AND Content IS NOT NULL
    """
    cursor = conn.cursor()
    cursor.execute(query)
    row = cursor.fetchone()
    if row:
        item_id, name, content = row
        print(f'Fetching {name} ({len(content)} bytes)')
        results = pbi_parser.parse_pbi_file(content, 'report.pbix')
        print(f'Quality: {results.get("source_quality", "")}')
        print(f'Measures: {len(results.get("measures", []))}')
        print(f'M Queries: {len(results.get("m_queries", {}))}')
        print(f'Relationships: {len(results.get("relationships", []))}')
        print(f'Tables: {len(results.get("tables", []))}')
    else:
        print('No row found')
except Exception as e:
    print(f'Error: {e}')
