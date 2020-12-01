import re
import sys
import requests

#
# Standalone script to batch download all plans from a EasyDMP instance
#

endpoint = sys.argv[0]
token = sys.argv[1]
dir = sys.argv[2]

r = requests.get('{}/api/v1/plans'.format(endpoint))
r.raise_for_status()
plans = r.json()
for plan in plans:
    pdf_url = plan.get('generated_pdf_url')
    if not pdf_url:
        continue
    pr = requests.get(pdf_url)
    pr.raise_for_status()
    d = pr.headers['Content-Disposition']
    fname = re.findall("filename=(.+)", d)[0]
    file = open("{}{}".format(dir, fname), "w")
    file.write(pr.content)
    file.close()
