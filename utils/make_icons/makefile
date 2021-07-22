all : \
	../../src/doc/images/photini_logo.png \
	../../src/photini/data/icons/photini_128.png \
	../../src/photini/data/icons/photini_48.png \
	../../src/photini/data/icons/photini_win.ico \
	../../src/photini/data/map_circle_blue.png \
	../../src/photini/data/map_circle_red.png

# scale master icon to any size
icon_%.pam : icon_master.png
	pngtopam -alphapam $< | \
	pamscale -width $* -height $* >$@

# create documentation logo
../../src/doc/images/photini_logo.png : icon_200.pam
	pamrgbatopng $< >$@

# create linux icons
../../src/photini/data/icons/photini_%.png : icon_%.pam
	mkdir -p $(dir $@)
	pamrgbatopng $< >$@

# create windows icon file with several sizes
../../src/photini/data/icons/photini_win.ico : \
		icon_256.pam icon_64.pam icon_48.pam \
		icon_32.pam icon_24.pam icon_16.pam
	cat $? | \
	pamtowinicon >$@

# convert alpha image to RGBA png
../../src/photini/data/map_%_blue.png : %_alpha.pgm
	ppmmake rgb:33/88/ff 11 11 | \
	pamstack -tupletype=RGB_ALPHA - $< | \
	pamtopng >$@

../../src/photini/data/map_%_red.png : %_alpha.pgm
	ppmmake rgb:ff/00/00 11 11 | \
	pamstack -tupletype=RGB_ALPHA - $< | \
	pamtopng >$@

# render XFIG drawing
%_alpha.pgm : %.fig
	fig2dev -L ppm -b 15 $< | \
	ppmtopgm | \
	pnminvert | \
	pamscale -width 11 -height 11 >$@
