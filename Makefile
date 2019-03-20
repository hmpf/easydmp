.PHONY: clean bigclean refresh

refresh:
	touch ./src/easydmp/site/wsgi.py

clean:
	-find . -name __pycache__ -print0 | xargs -0 rm -rf
	-find . -name "*.pyc" -print0 | xargs -0 rm -rf
	-find . -name "*.egg-info" -print0 | xargs -0 rm -rf
	-rm -rf src/easydmp/dmpt/static/cached/dmpt/*
	-rm -rf .coverage
	-rm -rf htmlcov
	-rm -rf build
	-rm -rf dist

bigclean: clean
	-rm -rf .tox
	-find . -name 'db.sqlite3' -print0 | xargs -0 rm -rf
