import zipfile
import io
import re
import logging

import json

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
            
            # 1. Advanced JSON DataModelSchema Extraction (Modern PBIX/PBIT)
            if "DataModelSchema" in results["package_items"]:
                schema_data = z.read("DataModelSchema").decode('utf-16', errors='ignore')
                try:
                    schema_json = json.loads(schema_data)
                    model = schema_json.get("model", {})
                    for table in model.get("tables", []):
                        table_name = table.get("name", "Unknown")
                        columns = [c.get("name") for c in table.get("columns", [])]
                        results["tables"].append({"name": table_name, "columns": columns})
                        
                        for measure in table.get("measures", []):
                            results["measures"].append({
                                "name": measure.get("name"),
                                "expression": measure.get("expression", ""),
                                "table": table_name
                            })
                            
                        # Extract Native SQL/M-Query from Partitions
                        for partition in table.get("partitions", []):
                            source = partition.get("source", {})
                            if source.get("type") == "m":
                                expr = source.get("expression", [])
                                if isinstance(expr, list):
                                    expr = "\n".join(expr)
                                
                                # Clean up Power Query special characters like #(lf) and #(tab)
                                clean_expr = expr.replace("#(lf)", "\n").replace("#(tab)", "\t").replace("#(cr)", "\r")
                                
                                # 1. Extract Native SQL
                                sql_match = re.search(r'Query\s*=\s*\"(.*?)\"', clean_expr, re.IGNORECASE | re.DOTALL)
                                if sql_match:
                                    sql_query = sql_match.group(1).replace('""', '"')
                                    results["m_queries"][f"{table_name}_SQL"] = sql_query
                                else:
                                    results["m_queries"][f"{table_name}_MQuery"] = clean_expr[:500] + "..."

                                # 2. Extract Data Source Info (Server/DB)
                                ds_match = re.search(r'Sql\.Database\s*\(\s*\"(.*?)\"\s*,\s*\"(.*?)\"', clean_expr, re.IGNORECASE)
                                if ds_match:
                                    results["data_sources"] = results.get("data_sources", [])
                                    ds_info = {"server": ds_match.group(1), "database": ds_match.group(2)}
                                    if ds_info not in results["data_sources"]:
                                        results["data_sources"].append(ds_info)
                except Exception as e:
                    logging.error(f"DataModelSchema parse error: {e}")
            
            # 1.5 Fallback DAX Extraction (Legacy DataModel Binary)
            elif "DataModel" in results["package_items"]:
                dm = z.read("DataModel")
                patterns = re.findall(b'M\x00e\x00a\x00s\x00u\x00r\x00e\x00.\x00([A-Za-z0-9_\ ]{1,100})\x00\x00\x12', dm)
                for p in patterns:
                    name = p.decode('utf-16', errors='ignore').strip()
                    if name: results["measures"].append({"name": name, "expression": "Binary extracted (Expression masked)"})

            # 2. M-Query Extraction (The 'Aylık Churn' BIDB Fix)
            if "DataMashup" in results["package_items"]:
                mashup = z.read("DataMashup")
                pk_indices = [m.start() for m in re.finditer(b'PK\x03\x04', mashup)]
                for idx in pk_indices:
                    try:
                        with zipfile.ZipFile(io.BytesIO(mashup[idx:])) as mz:
                            if "Formulas/Section1.m" in mz.namelist():
                                m_code = mz.read("Formulas/Section1.m").decode('utf-8', errors='ignore')
                                queries = re.findall(r'shared\s+(.+?)\s*=\s*let', m_code)
                                for q in queries:
                                    results["m_queries"][q.strip()] = "Let...In Script Captured"
                                logging.info(f"Found {len(results['m_queries'])} hidden M-Queries in Mashup.")
                    except: continue

            # 3. Layout JSON Parsing (For visual metadata when no DataModel is present)
            if "Report/Layout" in results["package_items"]:
                layout = z.read("Report/Layout").decode('utf-16', errors='ignore')
                # Try to extract via json first, fallback to regex
                extracted_entities = set()
                try:
                    layout_json = json.loads(layout)
                    # Convert to string to find all 'Entity' keys easily without deep recursion
                    layout_str = json.dumps(layout_json)
                    entities = re.findall(r'\"Entity\":\s*\"(.*?)\"', layout_str)
                    extracted_entities.update(entities)
                    
                    # Also look for queryRef which gives table.column
                    query_refs = re.findall(r'\"queryRef\":\s*\"(.*?)\"', layout_str)
                    for ref in query_refs:
                        if "." in ref:
                            extracted_entities.add(ref.split(".")[0])
                except:
                    # Regex fallback for broken JSON
                    entities = re.findall(r'\"Entity\":\s*\"(.*?)\"', layout)
                    extracted_entities.update(entities)
                
                # If we didn't find tables via DataModelSchema, use Layout Entities
                if not results["tables"]:
                    results["tables"] = [{"name": t} for t in extracted_entities if t]

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
