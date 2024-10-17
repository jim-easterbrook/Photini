all : \
	../../src/doc/images/photini_logo.png \
	../../src/photini/data/icons/photini_128.png \
	../../src/photini/data/icons/photini_48.png \
	../../src/photini/data/icons/photini_win.ico \
	../../src/photini/data/icons/photini.icns

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

# create macOS icons file with several sizes
# requires icns-utils linux package
../../src/photini/data/icons/%.icns : \
		%.iconset/icon_16x16.png %.iconset/icon_16x16@2x.png \
		%.iconset/icon_32x32.png %.iconset/icon_32x32@2x.png \
		%.iconset/icon_64x64.png %.iconset/icon_64x64@2x.png \
		%.iconset/icon_128x128.png %.iconset/icon_128x128@2x.png \
		%.iconset/icon_256x256.png %.iconset/icon_256x256@2x.png \
		%.iconset/icon_512x512.png %.iconset/icon_512x512@2x.png
	icnsutil -c icns -o $@ $*.iconset
	rm -rf $*.iconset

photini.iconset/icon_%.png : icon_master.png
	mkdir -p photini.iconset
	declare spec=$* && \
	declare scale=$${spec#*@} && \
	declare size=$${spec%%x*} && \
	if [[ "2x" == $$scale ]]; then let "size = $$size * 2"; fi && \
	pngtopam -alphapam $< | \
	pamscale -width $$size -height $$size | \
	pamtopng | \
	pngquant --quality=60 - >$@
