import sys
from portal_vision_agent import PortalVisionAgent
import os

agent = PortalVisionAgent()
res = agent.capture_report_screen("https://www.google.com", "vision_test.png")
print(f"STATUS: {res['status']}")
if "error" in res: print(f"ERROR: {res['error']}")
