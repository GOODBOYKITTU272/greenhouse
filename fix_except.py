with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace('''
                answer = response.choices[0].message.content.strip()

        # ZERO-TOUCH BUSINESS FILTERS
''', '''
                answer = response.choices[0].message.content.strip()
            except Exception as e:
                print("OpenAI Error:", e)
                answer = ""

        # ZERO-TOUCH BUSINESS FILTERS
''')

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
