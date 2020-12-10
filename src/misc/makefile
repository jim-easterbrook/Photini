all : \
	../doc/images/photini_logo.png \
	../photini/data/icons/photini_128.png \
	../photini/data/icons/photini_48.png \
	../photini/data/icons/photini_win.ico \

# scale master icon to any size
icon_%.pam : icon_master.png
	pngtopam -alphapam $< | \
	pamscale -width $* -height $* >$@

# create documentation logo
../doc/images/photini_logo.png : icon_200.pam
	pamrgbatopng $< >$@

# create linux icons
../photini/data/icons/photini_%.png : icon_%.pam
	mkdir -p $(dir $@)
	pamrgbatopng $< >$@

# create windows icon file with several sizes
../photini/data/icons/photini_win.ico : icon_256.pam icon_64.pam icon_48.pam \
		icon_32.pam icon_24.pam icon_16.pam
	cat $? | \
	pamtowinicon >$@
