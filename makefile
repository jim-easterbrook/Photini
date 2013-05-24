all : code/photini/data/LICENSE.txt doc
	python setup.py build

install : all
	python setup.py install

dist : all
	python setup.py sdist

clean :
	rm -Rf doc build dist

doc :
	$(MAKE) -C doc_src html

.PHONY : doc dist

code/photini/data/LICENSE.txt : LICENSE.txt
	cp -p $< $@
