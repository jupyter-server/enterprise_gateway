fname=gateway_kernel_init_sequence_diagram
all:
	make tex
	make clean_tmp
tex:
	xelatex -shell-escape ${fname}
clean_tmp:
	rm -f *.aux *.dvi *.idx *.ilg *.ind *.log *.nav *.out *.snm *.xdv *.toc *~
	rm -rf .texpadtmp
clean:
	make clean_tmp
	rm -f *.pdf *.png

