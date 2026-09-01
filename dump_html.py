import requests
from bs4 import BeautifulSoup

url = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"
r = requests.get(url)
soup = BeautifulSoup(r.text, 'html.parser')

inputs = soup.find_all('input')
for i in inputs:
    print(f"ID: {i.get('id')} | Name: {i.get('name')} | Type: {i.get('type')} | Aria-Label: {i.get('aria-label')}")

