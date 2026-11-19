import requests
from bs4 import BeautifulSoup

login_url = 'http://10.87.1.231/Identity/Account/Login'

session = requests.Session()

response = session.get(login_url)
soup = BeautifulSoup(response.text, 'html.parser')
token_input = soup.find('input', attrs={'name': '__RequestVerificationToken'})

if token_input:
    token = token_input['value']
    payload = {
        'Input.UserID': 'T00773',
        'Input.Password': 'Takaya2026@',
        '__RequestVerificationToken': token,
        'Input.RememberMe': 'false'
    }

    login_response = session.post(login_url, data=payload)
    print(f"Login Status Code: {login_response.status_code}")
else:
    print("Could not find the __RequestVerificationToken on the page.")


scan_url = 'http://10.87.1.231/OQC/AddScan'
response = session.post(scan_url, data={
    'OQCJobId': 749,
    'serialNumber': '5B23Y2200010807'
})

with open('test.html', 'w', encoding='utf-8') as f:
    f.write(response.text)
