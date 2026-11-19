# Keep TeX auxiliary files out of the paper source directory.
.PHONY: pdf
pdf:
	mkdir -p build
	pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
	bibtex build/main
	pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
	pdflatex -interaction=nonstopmode -halt-on-error -output-directory=build main.tex
	cp build/main.pdf main.pdf
