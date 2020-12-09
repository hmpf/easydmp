import datetime
import re
import sys
import requests

#
# Standalone script to batch download all plans from an EasyDMP instance
#

endpoint = sys.argv[1]
token = sys.argv[2]
dir = sys.argv[3]

added_ts_format = '%Y-%m-%dT%H:%M:%S.%fZ'
from_date = datetime.datetime.strptime(sys.argv[4], added_ts_format) if len(sys.argv) >= 5 else None
to_date = datetime.datetime.strptime(sys.argv[5], added_ts_format) if len(sys.argv) >= 6 else None

auth_headers = {'Authorization': 'Bearer {}'.format(token)}
print('Getting plans from {}'.format(endpoint))
if from_date:
    print('From date: {}'.format(from_date))
if to_date:
    print('To date: {}'.format(to_date))
r = requests.get('{}/api/v2/plans'.format(endpoint), headers=auth_headers)
r.raise_for_status()
plans = r.json()
print('Saving {} plans to {}'.format(len(plans), dir))
for plan in plans:
    pdf_url = '{}/api/v2/plans/{}/export.pdf'.format(endpoint, plan['id'])
    pr = requests.get(pdf_url, headers=auth_headers)
    pr.raise_for_status()
    cd = pr.headers['Content-Disposition']
    with open("{}/{}".format(dir, re.findall('filename=(.+)', cd)[0]), 'wb') as f:
        f.write(pr.content)
