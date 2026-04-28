import time
import os
import logging
from playwright.sync_api import sync_playwright

class PortalVisionAgent:
    def __init__(self, profile_dir=".pw-raportal-profile"):
        self.profile_dir = profile_dir

    def capture_report_screen(self, report_url, output_path):
        res = {"status": "screenshot_failed", "error": "", "path": str(output_path)}
        
        if not report_url or "None" in str(report_url):
            res["status"] = "screenshot_failed_no_report_url"
            return res

        try:
            with sync_playwright() as p:
                try:
                    # Persistent context preserves the session
                    browser = p.chromium.launch_persistent_context(self.profile_dir, headless=True)
                    logging.info("Persistent browser context active.")
                except Exception as b_err:
                    logging.warning(f"Profile locked, using temp instance: {b_err}")
                    # If this happens, we might need to re-login in the temp instance
                    browser = p.chromium.launch(headless=True)
                    browser = browser.new_context()
                
                page = browser.new_page()
                
                # NAVIGATION WITH LOGIN HANDLING
                logging.info(f"Navigating to: {report_url}")
                page.goto(report_url, wait_until="domcontentloaded", timeout=60000)
                
                # Check for Kariyer.net Login Page
                if "Account/Login" in page.url or "login" in page.url.lower():
                    logging.info("Login wall detected. Performing automated authentication...")
                    try:
                        # Kariyer.net / Raportal Standard Login Selectors
                        page.fill("input[name*='User']", "esra.akinci")
                        page.fill("input[name*='Pass']", "Ea93934430.")
                        page.click("button[type='submit'], input[type='submit']")
                        page.wait_for_load_state("networkidle", timeout=30000)
                        logging.info("Login successful. Continuing to report...")
                    except Exception as l_err:
                        logging.error(f"Automated login failed: {l_err}")

                # WAIT FOR PBI VISUALS
                page.wait_for_load_state("networkidle", timeout=60000)
                time.sleep(20) 
                
                try:
                    page.screenshot(path=str(output_path), full_page=False)
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
                        res["status"] = "screenshot_success"
                        res["path"] = str(output_path)
                        res["size_bytes"] = os.path.getsize(output_path)
                    else:
                        res["status"] = "screenshot_failed_empty"
                except Exception as te:
                    res["status"] = "screenshot_failed_timeout"
                    res["error"] = str(te)
                
                browser.close()
                return res
        except Exception as e:
            res["status"] = "screenshot_failed_critical"
            res["error"] = str(e)
            return res
