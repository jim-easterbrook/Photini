all : code/photini/version.py code/photini/data/LICENSE.txt doc
	python setup.py build

install : all
	python setup.py install

dist : all
	python setup.py sdist

clean :
	rm -Rf doc build dist

doc :
	$(MAKE) -C code/doc_src html

.PHONY : doc dist code/photini/version.py

COMMIT	:= $(shell git rev-parse --short master)
code/photini/version.py :
	date +"version = '%y.%m'" >$@
	echo "release = '$(COMMIT)'" >>$@

code/photini/data/LICENSE.txt : LICENSE.txt
	cp -p $< $@
