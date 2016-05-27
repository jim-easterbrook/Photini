all : \
	../doc/images/photini_logo.png \
	../photini/data/icons/128/photini.png \
	../photini/data/icon_48.png \
	../windows/icon.ico \

# scale master icon to any size
icon_%.pam : icon_master.png
	pngtopam -alphapam $< | \
	pamscale -width $* -height $* >$@

# create linux icons
../doc/images/photini_logo.png : icon_200.pam
	pamrgbatopng $< >$@

../photini/data/icons/%/photini.png : icon_%.pam
	mkdir -p $(dir $@)
	pamrgbatopng $< >$@

../photini/data/icon_%.png : icon_%.pam
	pamrgbatopng $< >$@

# create windows icon file with several sizes
../windows/%.ico : %_256.pam %_64.pam %_48.pam %_32.pam %_24.pam %_16.pam
	cat $? | \
	pamtowinicon >$@
