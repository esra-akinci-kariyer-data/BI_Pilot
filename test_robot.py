import sys, os, pbi_robot_engine
sys.stdout.reconfigure(encoding='utf-8')
pbix = os.path.abspath(r'temp_pbix\_Satışlar.pbix')
pbit = os.path.abspath(r'temp_pbix\_Satışlar.pbit')
print('PBIX=', pbix)
res = pbi_robot_engine.trigger_pbi_robot_export(pbix, pbit)
print('Sonuc=', res)