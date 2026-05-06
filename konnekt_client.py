import requests
import os

class KonnektAPIClient:
    def __init__(self, base_url="https://test-konnekt-api-k8s.kariyer.net"):
        self.base_url = base_url.rstrip("/")
        self.upload_url = f"{self.base_url}/api/v1/powerbi/upload"
        self.reports_url = f"{self.base_url}/api/v1/powerbi/reports"

    def upload_pbix(self, file_bytes, filename):
        """
        Uploads a PBIX/PBIT file to Konnekt API for parsing.
        Returns the parsed JSON data.
        """
        files = {"file": (filename, file_bytes, "application/octet-stream")}
        try:
            response = requests.post(self.upload_url, files=files, timeout=300)
            if response.status_code == 200:
                return True, response.json()
            else:
                return False, f"API Error ({response.status_code}): {response.text}"
        except Exception as e:
            return False, f"Connection Exception: {str(e)}"

    def get_report_metadata(self, report_id):
        """
        Fetches detailed metadata for an already uploaded report.
        """
        try:
            results = {}
            # Fetch tables
            resp_tables = requests.get(f"{self.reports_url}/{report_id}/tables")
            if resp_tables.status_code == 200:
                results['tables'] = resp_tables.json()
            
            # Fetch measures
            resp_measures = requests.get(f"{self.reports_url}/{report_id}/measures")
            if resp_measures.status_code == 200:
                results['measures'] = resp_measures.json()

            # Fetch lineage
            resp_lineage = requests.get(f"{self.reports_url}/{report_id}/lineage")
            if resp_lineage.status_code == 200:
                results['lineage'] = resp_lineage.json()
                
            return True, results
        except Exception as e:
            return False, str(e)

    def list_connections(self):
        """List registered Power BI connections in Konnekt."""
        try:
            resp = requests.get(f"{self.base_url}/api/v1/powerbi/connections")
            if resp.status_code == 200:
                return True, resp.json()
            return False, f"Error: {resp.status_code}"
        except Exception as e:
            return False, str(e)

    def create_pbirs_connection(self, name, server_url, username, password, domain="KARIYER"):
        """Register a new PBIRS (Raportal) connection in Konnekt."""
        payload = {
            "name": name,
            "server_url": server_url,
            "username": username,
            "password": password,
            "domain": domain,
            "connection_type": "PBIRS",
            "auth_type": "NTLM"
        }
        try:
            resp = requests.post(f"{self.base_url}/api/v1/powerbi/connections", json=payload)
            if resp.status_code in [200, 201]:
                return True, resp.json()
            return False, f"API Error ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, str(e)

    def start_connection_scan(self, connection_id):
        """Trigger a scan for a specific connection."""
        try:
            resp = requests.post(f"{self.base_url}/api/v1/powerbi/connections/{connection_id}/scan")
            if resp.status_code in [200, 202]:
                return True, resp.json()
            return False, f"Scan Error ({resp.status_code}): {resp.text}"
        except Exception as e:
            return False, str(e)

    def search_report_in_konnekt(self, report_name):
        """Search for a report by name in Konnekt's scanned database."""
        try:
            resp = requests.get(self.reports_url)
            if resp.status_code == 200:
                reports = resp.json()
                # Find matching report
                match = next((r for r in reports if r.get('name') == report_name), None)
                return True, match
            return False, f"Search Error: {resp.status_code}"
        except Exception as e:
            return False, str(e)
