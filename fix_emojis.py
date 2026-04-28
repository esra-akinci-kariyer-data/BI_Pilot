import re

path = r'c:\Users\esra.akinci\OneDrive - Kariyer.net\Masaüstü\AI\raportal_agent_poc\raportal_agent_tema_revizeli.py'

with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    # known mojibake emojis
    'ðŸ”Ž': '🔎',
    'ðŸ”—': '🔗',
    'ðŸ—‚ï¸': '🗂️',
    'ðŸ“📊': '📊',
    'ðŸ§²': '🧲',
    'ðŸ”„': '🔄',
    'ðŸ’¡': '💡',
    'ðŸš€': '🚀',
    'ðŸŽ¯': '🎯',
    'ðŸ‘‹': '👋',
    'ðŸ”’': '🔒',
    'ðŸ“Š': '📊',
    'ðŸ“š': '📚',
    'ðŸ” ': '🔍',
    'ðŸ“„': '📄',
    'ðŸ“‰': '📉',
    'ðŸ“¥': '📥',
    'ðŸ—ï¸': '🏗️',
    'ðŸ—„ï¸': '🗄️',
    'ðŸ“Œ': '📌',
    'ðŸ“¦': '📦',
    'ðŸ“‹': '📋',
    'ðŸ¤–': '🤖',
    'ðŸ§¬': '🧬',
    'ðŸŒ ': '🌐', 
    'ðŸ“ˆ': '📈',
    'ðŸ“œ': '📜',
    'ðŸ” ': '🔐',
    'ðŸŽ‰': '🎉',

    # Also fixes specific to "Aç" misencodings
    'ðŸ”— Aç': '🔗 Aç',
    'ðŸ”— Açç': '🔗 Aç',

    # In case there are `dY"?` strings exactly from the previous run
    r'dY"\? Rapor listesinde ara...': '🔎 Rapor listesinde ara...',
    r'dY"\? Aç': '🔗 Aç'
}

for k, v in replacements.items():
    if '\\' in k or '?' in k: # Handle regex
        text = re.sub(k, v, text)
    else:
        text = text.replace(k, v)

# Fix weird Turkish characters that usually happen in CP1252 to UTF-8
turkish_repl = {
    'Ã¼': 'ü', 'Ä±': 'ı', 'ÅŸ': 'ş', 'Ã§': 'ç', 'Ã¶': 'ö', 'ÄŸ': 'ğ',
    'Ä°': 'İ', 'Ã–': 'Ö', 'Ãœ': 'Ü', 'Ã‡': 'Ç', 'Äž': 'Ğ',
    'â€”': '—', 'Â ': ' '
}

for k, v in turkish_repl.items():
    text = text.replace(k, v)

# A final pass on "Aç" combinations that are wrong.
text = re.sub(r'dY".*?\s*Aç', '🔗 Aç', text)
text = re.sub(r'ðŸ”.*?\s*Aç', '🔗 Aç', text)

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)

print("Safely fixed specific known mismatches.")
