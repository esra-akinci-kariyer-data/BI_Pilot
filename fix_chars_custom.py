import re

path = r'c:\Users\esra.akinci\OneDrive - Kariyer.net\Masaüstü\AI\raportal_agent_poc\raportal_agent_tema_revizeli.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

replacements = {
    # Turkish characters that might be broken
    'Ã¼': 'ü', 'Ä±': 'ı', 'ÅŸ': 'ş', 'Ã§': 'ç', 'Ã¶': 'ö', 'ÄŸ': 'ğ',
    'Ä°': 'İ', 'Ã–': 'Ö', 'Ãœ': 'Ü', 'Ã‡': 'Ç', 'Äž': 'Ğ',
    'â€”': '—', 'Â ': ' ', 'â€¢': '•', 'ï¸': '', 'â…': '', 
    'A': 'Aç', 'AÃ§': 'Aç', 'Ã§': 'ç',

    # Fixed strings seen in screenshot or code
    r'dY"\? Rapor listesinde ara...': '🔎 Rapor listesinde ara...',
    r'dY"\?': '📁', # Some are folders? The user screenshot has folder icon then Tüm Rapor Kataloğu. Wait, the screenshot has: "🔎 Rapor listesinde ara...". So it's a search icon.
    r'dY"— Aç': '🔗 Aç',
    r'dY"Aç': '🔗 Aç',
    r'dY”—': '🔗',
    r'dY"': '🔗', # If generic dY" is a link or something.
    'AçA,A?': 'Aç',
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
    'ðŸ”': '🔍',
    'ðŸ“„': '📄',
    'ðŸ“‰': '📉',
    'ðŸ“¥': '📥',
    'ðŸ—ï¸': '🏗️',
    'ðŸ”Ž': '🔍',
    'ðŸ—„ï¸': '🗄️',
    'ðŸ“Œ': '📌',
    'ðŸ“¦': '📦',
    'ðŸ“‹': '📋',
    'ðŸ¤–': '🤖',
    'ðŸ§¬': '🧬',
    'ðŸŒ': '🌐', 
    'ðŸ”Ž': '🔎',
    'ðŸ“ˆ': '📈',
    'ðŸ“œ': '📜',
    'ðŸ”': '🔐',
    'ðŸŽ‰': '🎉',
    'âœ…': '✅',
    'âš ï¸': '⚠️',
    'â„¹ï¸': 'ℹ️',
    'â­': '⭐',
    'âž•': '➕',
    'Aç\x8f\x8e\x8f\x8e': 'Aç',
    'dY\x0f-': '🚀',
    r'dY"â€”': '📊'
}

for old, new in replacements.items():
    if old.startswith('r') or '\\' in old:
        # Regex replacement? No, let's keep it simple string replace first, but handle regex explicit strings.
        content = re.sub(old, new, content)
    else:
        content = content.replace(old, new)


# For the specific 'dY"? Rapor listesinde ara...'
content = content.replace('dY"? Rapor listesinde ara...', '🔎 Rapor listesinde ara...')

# Fix weird variations of 'Aç' in tables:
# E.g. 'ðŸ”— Aç', 'dY"" Aç', etc.
content = re.sub(r'dY".*?\s*Aç', '🔗 Aç', content)
content = re.sub(r'ðŸ”.*?\s*Aç', '🔗 Aç', content)
content = re.sub(r'ðŸ.*?\s*Aç', '🔗 Aç', content)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Characters fixed.")
