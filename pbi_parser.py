import zipfile
import io
import re
import logging

def parse_pbi_file(file_bytes, filename=""):
    """Nuclear PBIX Parser: Extracts DAX measures and scans for hidden M-Queries."""
    results = {
        "measures": [],
        "m_queries": {},
        "tables": [],
        "package_items": [],
        "filename": filename
    }
    
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            results["package_items"] = z.namelist()
            
            # 1. DAX Extraction (Standard DataModel)
            if "DataModel" in results["package_items"]:
                dm = z.read("DataModel")
                # Scavenge DAX measures (re.finditer for UTF-16 patterns)
                patterns = re.findall(b'M\x00e\x00a\x00s\x00u\x00r\x00e\x00.\x00([A-Za-z0-9_\ ]{1,100})\x00\x00\x12', dm)
                for p in patterns:
                    name = p.decode('utf-16', errors='ignore').strip()
                    if name: results["measures"].append({"name": name, "expression": "Binary extracted (Expression masked)"})

            # 2. M-Query Extraction (The 'Aylık Churn' BIDB Fix)
            if "DataMashup" in results["package_items"]:
                mashup = z.read("DataMashup")
                # SEARCH FOR HIDDEN ZIP (PK PK) INSIDE DataMashup
                # This is formulas.zip
                pk_indices = [m.start() for m in re.finditer(b'PK\x03\x04', mashup)]
                for idx in pk_indices:
                    try:
                        with zipfile.ZipFile(io.BytesIO(mashup[idx:])) as mz:
                            if "Formulas/Section1.m" in mz.namelist():
                                m_code = mz.read("Formulas/Section1.m").decode('utf-8', errors='ignore')
                                # Parse out shared queries
                                queries = re.findall(r'shared\s+(.+?)\s*=\s*let', m_code)
                                for q in queries:
                                    results["m_queries"][q.strip()] = "Let...In Script Captured"
                                logging.info(f"Found {len(results['m_queries'])} hidden M-Queries in Mashup.")
                    except: continue

            # 3. Table Scavenging
            if "Report/Layout" in results["package_items"]:
                layout = z.read("Report/Layout").decode('utf-16', errors='ignore')
                tables = re.findall(r'\"Entity\":\s*\"(.+?)\"', layout)
                results["tables"] = [{"name": t} for t in set(tables)]

    except Exception as e:
        results["error"] = str(e)
    
    return results

def convert_to_pbit_bytes(pbix_bytes):
    """Converts PBIX bytes to PBIT by removing the DataModel component."""
    try:
        in_buf = io.BytesIO(pbix_bytes)
        out_buf = io.BytesIO()
        with zipfile.ZipFile(in_buf, 'r') as zin:
            with zipfile.ZipFile(out_buf, 'w') as zout:
                for item in zin.infolist():
                    if item.filename != 'DataModel':
                        zout.writestr(item, zin.read(item.filename))
        return out_buf.getvalue()
    except:
        return pbix_bytes # Fallback
