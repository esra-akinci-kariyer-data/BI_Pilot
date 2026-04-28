import os
import json
import datetime
import logging
from pathlib import Path
from pbi_parser import parse_pbi_file
from pbi_live_bridge import silent_pbi_extract

class PBIDiagnosticEngine:
    def __init__(self, output_root="outputs"):
        self.run_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_dir = Path(output_root) / f"run_{self.run_id}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "screenshots").mkdir(exist_ok=True)
        (self.output_dir / "logs").mkdir(exist_ok=True)
        self.setup_logging()
        
        self.status = {
            "run_id": self.run_id,
            "overall_status": "Starting",
            "phases": {}
        }

    def setup_logging(self):
        log_file = self.output_dir / "logs" / "extraction_log.txt"
        h = logging.FileHandler(str(log_file), mode='w', encoding='utf-8')
        h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
        logging.getLogger().addHandler(h)
        logging.getLogger().setLevel(logging.INFO)

    def save_status(self):
        with open(self.output_dir / "run_status.json", "w", encoding="utf-8") as f:
            json.dump(self.status, f, indent=2, ensure_ascii=False)

    def analyze_report(self, report_name, report_url, pbix_bytes=None, ui_callback=None):
        logging.info(f"--- Starting Analysis: {report_name} ---")
        tech = {"status": "starting", "failure_reasons": [], "measures": [], "m_queries": {}}
        
        # Phase 1: Package Analysis
        if pbix_bytes:
            data = parse_pbi_file(pbix_bytes, f"{report_name}.pbix")
            tech.update(data)
            logging.info(f"Forensic results: {len(data.get('measures',[]))} measures found.")
            
            # Scavenge tables from binary if empty
            if not tech.get("tables"):
                import re
                # Look for UTF-16 patterns for table names
                table_patterns = re.findall(b'\x00([A-Z][a-zA-Z0-9_\ ]{2,30})\x00\x00\x12', pbix_bytes)
                if table_patterns:
                    tech["tables"] = [{"name": p.decode('utf-16', errors='ignore').strip()} for p in table_patterns if len(p) > 4]
                    logging.info(f"Binary Scavenger found {len(tech['tables'])} potential tables.")

            # Evidence for Live Connection
            items = data.get("package_items", [])
            if "DataModel" not in items:
                if "Connections" in items:
                    tech["failure_reasons"].append("KANIT: 'Connections' dosyası var ama 'DataModel' yok. Bu teknik olarak bir Thin Report / Live Connection raporudur.")
                else:
                    tech["failure_reasons"].append("OLASI THIN REPORT: Yerel veri modeli (DataModel) pakette bulunamadı.")
        
        # Phase 2: XMLA Bridge
        if pbix_bytes and not tech["measures"]:
            if ui_callback: ui_callback("🌉 XMLA Tüneli deneniyor...")
            tmp = self.output_dir / "temp.pbix"
            with open(tmp, "wb") as f: f.write(pbix_bytes)
            deep = silent_pbi_extract(str(tmp.absolute()), status_update_func=ui_callback)
            if deep and "error" not in deep:
                tech.update(deep)
                tech["status"] = "xmla_success"
            else:
                tech["failure_reasons"].append(f"XMLA Error: {deep.get('error') if deep else 'Timeout'}")
            try: os.remove(tmp)
            except: pass

        self.status["phases"]["technical"] = tech
        self.save_status()
        return tech
