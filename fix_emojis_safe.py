import re

path = r'c:\Users\esra.akinci\OneDrive - Kariyer.net\Masaüstü\AI\raportal_agent_poc\raportal_agent_tema_revizeli.py'

with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

changes = 0

# Fix Rapor listesinde ara
if 'ðŸ”Ž Rapor listesinde ara...' in text:
    text = text.replace('ðŸ”Ž Rapor listesinde ara...', '🔎 Rapor listesinde ara...')
    changes += 1

if 'ðŸ”— Aç' in text:
    text = text.replace('ðŸ”— Aç', '🔗 Aç')
    changes += 1

if 'ðŸ—‚ï¸ Tüm Rapor Kataloğu' in text:
    text = text.replace('ðŸ—‚ï¸ Tüm Rapor Kataloğu', '🗂️ Tüm Rapor Kataloğu')
    changes += 1

# Catch any raw double encodings of those two symbols just in case
if 'ðŸ”Ž' in text:
    text = text.replace('ðŸ”Ž', '🔎')
    changes += 1

if 'ðŸ”—' in text:
    text = text.replace('ðŸ”—', '🔗')
    changes += 1

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print(f"Num changes applied: {changes}")
