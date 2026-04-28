import os
import re
import socket
import json
import logging
import subprocess
import time
import io
import tempfile
from html import unescape

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_active_pbi_ports():
    """Aggressive scan for all possible Analysis Services ports in LocalAppData."""
    ports = []
    local_app_data = os.getenv('LOCALAPPDATA')
    search_root = os.path.join(local_app_data, 'Microsoft')
    if not os.path.exists(search_root): return []
    
    for root, dirs, files in os.walk(search_root):
        if 'msmdsrv.port.txt' in files:
            port_file = os.path.join(root, 'msmdsrv.port.txt')
            try:
                mtime = os.path.getmtime(port_file)
                with open(port_file, 'r', encoding='utf-16') as f:
                    port = f.read().strip()
                    if port.isdigit():
                        ports.append({
                            "port": int(port),
                            "title": os.path.basename(os.path.dirname(root)),
                            "modified": mtime
                        })
            except: pass
    ports.sort(key=lambda x: x['modified'], reverse=True)
    return ports

def xmla_query(port, query_type="Measures", catalog=None):
    """Direct XMLA SOAP query via socket."""
    catalog_xml = f"<Catalog>{catalog}</Catalog>" if catalog else "<Catalog></Catalog>"
    soap_templates = {
        "Catalogs": '<Discover xmlns="urn:schemas-microsoft-com:xml-analysis"><RequestType>DBSCHEMA_CATALOGS</RequestType><Restrictions /><Properties><PropertyList /></Properties></Discover>',
        "Measures": f'<Discover xmlns="urn:schemas-microsoft-com:xml-analysis"><RequestType>MDSCHEMA_MEASURES</RequestType><Restrictions /><Properties><PropertyList>{catalog_xml}</PropertyList></Properties></Discover>',
        "Tables": f'<Discover xmlns="urn:schemas-microsoft-com:xml-analysis"><RequestType>DBSCHEMA_TABLES</RequestType><Restrictions /><Properties><PropertyList>{catalog_xml}</PropertyList></Properties></Discover>',
        "MQueries": f'<Discover xmlns="urn:schemas-microsoft-com:xml-analysis"><RequestType>TMSCHEMA_PARTITIONS</RequestType><Restrictions /><Properties><PropertyList>{catalog_xml}</PropertyList></Properties></Discover>'
    }
    payload = f'<?xml version="1.0" encoding="UTF-8"?><SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema"><SOAP-ENV:Body>{soap_templates[query_type]}</SOAP-ENV:Body></SOAP-ENV:Envelope>'
    header = f"POST /xmla HTTP/1.1\r\nHost: localhost:{port}\r\nContent-Type: text/xml\r\nContent-Length: {len(payload)}\r\nSOAPAction: \"urn:schemas-microsoft-com:xml-analysis:Discover\"\r\n\r\n"
    try:
        with socket.create_connection(("localhost", port), timeout=5) as sock:
            sock.sendall((header + payload).encode('utf-8'))
            response = b""
            while True:
                chunk = sock.recv(8192)
                if not chunk: break
                response += chunk
            return response.decode('utf-8', errors='ignore')
    except: return ""

def query_pbi_metadata(port):
    """Parses XMLA into JSON with aggressive M-Query extraction."""
    results = {"tables": [], "measures": [], "relationships": [], "m_queries": {}, "source_type": "Direct XMLA Bridge (Nuclear)"}
    raw_c = xmla_query(port, "Catalogs")
    cat_match = re.search(r'<(?:[\w]+:)?CATALOG_NAME[^>]*>(.*?)</(?:[\w]+:)?CATALOG_NAME>', raw_c, re.IGNORECASE)
    catalog = unescape(cat_match.group(1)) if cat_match else None
    
    # 1. Measures
    raw_m = xmla_query(port, "Measures", catalog)
    rows = re.findall(r'<row>(.*?)</row>', raw_m, re.DOTALL | re.IGNORECASE)
    for row in rows:
        m_name = re.search(r'<(?:[\w]+:)?MEASURE_NAME[^>]*>(.*?)</(?:[\w]+:)?MEASURE_NAME>', row, re.IGNORECASE)
        m_exp = re.search(r'<(?:[\w]+:)?EXPRESSION[^>]*>(.*?)</(?:[\w]+:)?EXPRESSION>', row, re.IGNORECASE)
        m_group = re.search(r'<(?:[\w]+:)?MEASUREGROUP_NAME[^>]*>(.*?)</(?:[\w]+:)?MEASUREGROUP_NAME>', row, re.IGNORECASE)
        if m_name and m_exp:
            results["measures"].append({"name": unescape(m_name.group(1)), "expression": unescape(m_exp.group(1)), "table": unescape(m_group.group(1)) if m_group else ""})
            
    # 2. Aggressive M-Queries (Handle both QueryDefinition and Expression tags)
    raw_p = xmla_query(port, "MQueries", catalog)
    p_rows = re.findall(r'<row>(.*?)</row>', raw_p, re.DOTALL | re.IGNORECASE)
    for row in p_rows:
        p_name = re.search(r'<(?:[\w]+:)?Name[^>]*>(.*?)</(?:[\w]+:)?Name>', row, re.IGNORECASE)
        p_def = re.search(r'<(?:[\w]+:)?QueryDefinition[^>]*>(.*?)</(?:[\w]+:)?QueryDefinition>', row, re.IGNORECASE)
        if not p_def: p_def = re.search(r'<(?:[\w]+:)?Expression[^>]*>(.*?)</(?:[\w]+:)?Expression>', row, re.IGNORECASE)
        if p_name and p_def:
            results["m_queries"][unescape(p_name.group(1))] = unescape(p_def.group(1))
    
    # 3. Tables
    raw_t = xmla_query(port, "Tables", catalog)
    t_names = re.findall(r'<(?:[\w]+:)?TABLE_NAME[^>]*>(.*?)</(?:[\w]+:)?TABLE_NAME>', raw_t, re.IGNORECASE)
    for tn in t_names:
        name = unescape(tn)
        if not name.startswith("LocalDateTable"): results["tables"].append({"name": name, "columns": []})
    return results

def silent_pbi_extract(pbix_path, status_update_func=None):
    """Aggressive 120s background extraction with verbose logging."""
    def log(msg): 
        if status_update_func: status_update_func(msg)
    try:
        abs_path = os.path.abspath(pbix_path)
        # Deep search for PBIDesktop.exe
        pbi_exe = None
        for cp in [r"C:\Program Files\Microsoft Power BI Desktop\bin\PBIDesktop.exe", r"C:\Program Files\Microsoft Power BI Desktop SSRS\bin\PBIDesktop.exe"]:
            if os.path.exists(cp): pbi_exe = cp; break
        
        if pbi_exe: subprocess.Popen([pbi_exe, abs_path], shell=True)
        else: subprocess.Popen(['start', '/min', abs_path], shell=True)
        
        start_time = time.time()
        while time.time() - start_time < 120:
            time.sleep(5)
            ports = get_active_pbi_ports()
            if ports:
                log(f"🌉 Port bulundu ({ports[0]['port']})...")
                data = query_pbi_metadata(ports[0]['port'])
                if len(data.get("measures", [])) > 0 or len(data.get("m_queries", {})) > 0:
                    subprocess.run(['taskkill', '/F', '/IM', 'PBIDesktop.exe'], capture_output=True)
                    return data
            else: log(f"⏳ Port bekleniyor... ({int(time.time() - start_time)}sn)")
        return {"error": "Zaman aşımı: Veri bulunamadı."}
    except Exception as e: return {"error": str(e)}
