import argparse
import pathlib
import sys
import urllib

try:
    import requests
except ImportError:
    msg = 'Cannot find the library "requests". Install via "pip install requests"'
    print(msg, file=sys.stderr)
    sys.exit(1)


"""
Standalone script to batch download the pdf version of all plans from an
EasyDMP instance.
"""


def build_endpoint_pieces(endpoint, template_id=None, validated=None, from_date=None, to_date=None):
    urltuple = urllib.parse.urlsplit(endpoint)
    path = '/api/v2/plans/'
    queries = []
    if template_id:
        queries.append(f'template={template_id')
    if validated is True:
        queries.append(f'valid=yes')
    elif validated is False:
        queries.append(f'valid=no')
    if from_date:
        queries.append(f'added__gt={from_date}')
    if to_date:
        queries.append(f'added__lt={to_date}')
    query = '&'.join(queries)
    return urltuple.scheme, urltuple.netloc, path, query, ''


def build_pdfurl_pieces(endpoint, pk):
    urltuple = urllib.parse.urlsplit(endpoint)
    path = f'/api/v2/plans/{pk}/export.pdf'
    return urltuple.scheme, urltuple.netloc, path, '', ''


def dump_pdf(endpoint, token, dir, template_id=None, validated=False, from_date=None, to_date=None):
    auth_headers = {'Authorization': f'Bearer {token}'}
    url_pieces = build_endpoint_pieces(endpoint, template_id, validated, from_date, to_date)
    url = urllib.parse.urlunsplit(url_pieces)
    print(f'Getting plans from "{url}", saving PDF to {dir}')
    r = requests.get(url, headers=auth_headers)
    r.raise_for_status()
    plans = r.json()
    pathlib.Path(dir).mkdir(parents=True, exist_ok=True)
    for plan in plans:
        plan_id = str(plan['id'])
        template_id = plan['template_id']
        pdf_url = urllib.parse.urlunsplit(build_pdfurl_pieces(endpoint, plan_id))
        pr = requests.get(pdf_url, headers=auth_headers)
        pr.raise_for_status()
        filename = f't{template_id}-{plan_id}.pdf'
        with open(f"{dir}/{filename}", 'wb') as f:
            f.write(pr.content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Export plans made according to the RFK Sigma2DMP EasyDMP'
    )
    parser.add_argument('endpoint', help='Fetch from this endpoint')
    parser.add_argument('token', help='Authentication token')
    parser.add_argument('directory', help='Put the pdfs in this directory')
    parser.add_argument('-T', '--template', help='Only return plans made from the given template id')
    parser.add_argument('-c', '--validated', help='Only return complete and validated plans',
                        default=False, action='store_true')
    parser.add_argument('-f', '--from',
                        help='After the timestamp. format: 2019-09-30T23:59:59.00Z',
                        dest='from_date', default=None)
    parser.add_argument('-t', '--to',
                        help='Before the timestamp. format: 2019-09-30T23:59:59.00Z',
                        dest='to_date', default=None)
    args = parser.parse_args()
    endpoint = args.endpoint

    dump_pdf(args.endpoint, args.token, args.dir, args.template,
             args.validated, args.from_date, args.to_date)
