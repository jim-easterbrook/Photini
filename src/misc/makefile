all : \
	../windows/icon.ico \

# scale master icon to any size
icon_%.pam : icon_master.png
	pngtopam -alphapam $< | \
	pamscale -width $* -height $* >$@

# create windows icon file with several sizes
../windows/%.ico : %_256.pam %_64.pam %_48.pam %_32.pam %_24.pam %_16.pam
	cat $? | \
	pamtowinicon >$@
