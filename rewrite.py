import urllib.request
import re

with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Normalize all tabs to 4 spaces
text = text.replace('\t', '    ')

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
