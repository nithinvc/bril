.PHONY: all

clean:
	rm ssa_results.csv *.norm.csv ssa_plot.png

all: ssa_plot.png

ssa_results.csv: ssa_brench.toml
	brench $^ > $@

%.norm.csv: %.csv
	python normalize.py < $^ > $@

ssa_plot.png: ssa_plot.json ssa_results.norm.csv
	vl2png $< > $@
