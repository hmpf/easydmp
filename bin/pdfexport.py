import re
import sys
import requests

#
# Standalone script to batch download all plans from an EasyDMP instance
#

if len(sys.argv) < 4:
    print('Usage: pdfexport <endpoint> <token> <directory> [from_date] [to_date]')
    print('Time format: 2019-09-30T23:59:59.00Z')
    exit(0)

endpoint = sys.argv[1]
token = sys.argv[2]
dir = sys.argv[3]

from_date = sys.argv[4] if len(sys.argv) >= 5 else None
to_date = sys.argv[5] if len(sys.argv) >= 6 else None

auth_headers = {'Authorization': 'Bearer {}'.format(token)}
query = '?'
if from_date:
    query += 'added__gt={}&'.format(from_date)
if to_date:
    query += 'added__lt={}&'.format(to_date)
url = '{}/api/v2/plans{}'.format(endpoint, query)
print('Getting plans from {}, saving PDF to {}'.format(url, dir))
r = requests.get(url, headers=auth_headers)
r.raise_for_status()
plans = r.json()
for plan in plans:
    pdf_url = '{}/api/v2/plans/{}/export.pdf'.format(endpoint, plan['id'])
    pr = requests.get(pdf_url, headers=auth_headers)
    pr.raise_for_status()
    cd = pr.headers['Content-Disposition']
    with open("{}/{}".format(dir, re.findall('filename=(.+)', cd)[0]), 'wb') as f:
        f.write(pr.content)
