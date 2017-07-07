
bin/python:
	virtualenv .

bin/pip: bin/python

deps: bin/pip
	bin/pip install -r requirements.txt

test:	deps
	bin/tox

dist: bin/python
	bin/python setup.py sdist

clean:
	- rm -rf include bin lib local share build dist man pyramid_metrics.egg-info
	- rm pip-selfcheck.json
	- find . -type f -name "*.pyc" -delete
	- find . -type f -name "*.pyo" -delete 
