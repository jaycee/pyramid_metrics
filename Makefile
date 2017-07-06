
bin/pip:
	virtualenv .

pystatsd-telegraf:
	git clone https://github.com/jaycee/pystatsd-telegraf

deps: bin/pip pystatsd-telegraf
	bin/pip install -r requirements.txt

test:	deps
	bin/tox

dist:
	bin/python setup.py dist

clean:
	- rm -rf pystatsd-telegraf
	- rm -rf include bin lib local share build dist man
	- rm pip-selfcheck.json
	- find . -type f -name "*.pyc" -delete
	- find . -type f -name "*.pyo" -delete 
