with open('applywizz_brain.py', 'r') as f:
    lines = f.readlines()
with open('applywizz_brain.py', 'w') as f:
    for line in lines:
        f.write(line.replace('\t', '    '))
