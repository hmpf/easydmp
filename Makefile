.PHONY: clean testclean nuke refresh

refresh:
	touch ./src/easydmp/site/wsgi.py

clean:
	-find . -name __pycache__ -print0 | xargs -0 rm -rf
	-find . -name "*.pyc" -print0 | xargs -0 rm -rf
	-find . -name "*.egg-info" -print0 | xargs -0 rm -rf
	-rm -rf build
	-rm -rf dist

testclean: clean
	-rm -rf .coverag*
	-rm -rf htmlcov

nuke: testclean
	-rm -rf .tox
	-find . -name 'db.sqlite3' -print0 | xargs -0 rm -rf
