from os import path
import cmdy
from . import LOGGER
from .formula import Formula, Term, Aggr

def title_to_valid_path(title, allowed = '_-.()ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'):
	return ''.join(c if c in allowed else '_' for c in title)

def get_plot_type(formula, figtype):
	if isinstance(formula.Y, Aggr) and isinstance(formula.X, Aggr):
		if figtype in ('', None, 'scatter'):
			return figtype or 'scatter'
		raise TypeError("Don't know how to plot AGGREGATION ~ AGGREGATION using plots other than scatter")
	if isinstance(formula.Y, Aggr) and isinstance(formula.X, Term):
		if figtype in ('', None, 'col', 'bar', 'pie'):
			if figtype == 'bar':
				figtype = 'col'
			return (figtype or 'pie') if formula.X.name == '1' else (figtype or 'col')
		raise TypeError("Don't know how to plot AGGREGATION ~ CATEGORICAL using plots other than bar or pie")
	# all are terms, 'cuz we cannot have Term ~ Aggr
	# if isinstance(formula.Y, Term) and isinstance(formula.X, Term):
	if formula.Y.term['type'] == 'categorical' and formula.X.term['type'] == 'categorical':
		if figtype in ('', None, 'bar'):
			return figtype or 'bar'
		raise TypeError("Don't know how to plot CATEGORICAL ~ CATEGORICAL using plots other than bar")
	if formula.Y.term['type'] == 'continuous' and formula.X.term['type'] == 'categorical':
		if figtype in ('', None, 'violin', 'boxplot', 'histogram', 'density', 'freqpoly'):
			return figtype or 'violin'
		raise TypeError("Don't know how to plot CONTINUOUS ~ CATEGORICAL using plots other than violin or boxplot")
	if formula.Y.term['type'] == 'categorical' and formula.X.term['type'] == 'continuous':
		if figtype in ('', None, 'col', 'bar', 'pie'):
			if figtype == 'bar':
				figtype = 'col'
			return figtype or 'pie'
		raise TypeError("If you want to plot CATEGORICAL ~ CONTINUOUS, transpose CONTINUOUS ~ CATEGORICAL")
	if formula.Y.term['type'] == 'continuous' and formula.X.term['type'] == 'continuous':
		if formula.X.term['func'].__name__ == '_ONE':
			if figtype in ('', None, 'histogram', 'freqpoly', 'density'):
				return figtype or 'histogram'
			raise TypeError("Don't know how to plot distribution using plots other than histogram or density")
		if figtype in ('', None, 'scatter'):
			return figtype or 'scatter'
		raise TypeError("Don't know how to plot CONTINUOUS ~ CONTINUOUS using plots other than scatter")

class One:

	def __init__(self, formula, title, ggs, devpars, outdir, samples, figtype, passed):

		LOGGER.info("INSTANCE: {!r}".format(title))
		self.title     = title
		self.formula   = Formula(formula, samples, passed, title)
		self.outprefix = path.join(outdir, title_to_valid_path(title))
		self.devpars   = devpars
		self.ggs       = ggs
		self.datafile  = open(self.outprefix + '.txt', 'w')
		if isinstance(self.formula.Y, Aggr) and \
			((isinstance(self.formula.X, Term) and self.formula.Y.xgroup) or \
			isinstance(self.formula.X, Aggr)):
			self.datafile.write("{}\t{}\tGroup\n".format(
				self.formula.Y.name, self.formula.X.name))
		else:
			self.datafile.write("{}\t{}\n".format(
				self.formula.Y.name, self.formula.X.name))
		self.figtype = get_plot_type(self.formula, figtype)
		LOGGER.info("[{}] plot type: {}".format(self.title, self.figtype))
		LOGGER.debug("[{}] ggs: {}".format(self.title, self.ggs))
		LOGGER.debug("[{}] devpars: {}".format(self.title, self.devpars))

	def iterate(self, variant):
		# Y
		self.formula.run(variant, self.datafile)

	def summarize(self):
		LOGGER.info("[{}] Summarizing aggregations ...".format(self.title))
		self.formula.done(self.datafile)
		self.datafile.close()

	def plot(self, Rscript):
		LOGGER.info("[{}] Composing R code ...".format(self.title))
		rcode = """
			require('ggplot2')
			figtype = {figtype!r}

			plotdata = read.table(	paste0({outprefix!r}, '.txt'),
									header = TRUE, row.names = NULL, check.names = FALSE, sep = "\t")
			cnames = make.unique(colnames(plotdata))
			colnames(plotdata) = cnames

			bQuote = function(s) paste0('`', s, '`')

			png(paste0({outprefix!r}, '.', figtype, '.png'),
				height = {devpars[height]}, width = {devpars[width]}, res = {devpars[res]})
			if (length(cnames) > 2) {{
				aes_for_geom = aes_string(fill = bQuote(cnames[3]))
				aes_for_geom_color = aes_string(color = bQuote(cnames[3]))
				plotdata[,3] = factor(plotdata[,3], levels = rev(unique(as.character(plotdata[,3]))))
			}} else {{
				aes_for_geom = NULL
				aes_for_geom_color = NULL
			}}
			p = ggplot(plotdata, aes_string(y = bQuote(cnames[1]), x = bQuote(cnames[2])))
			xticks = theme(axis.text.x = element_text(angle = 60, hjust = 1))
			if (figtype == 'scatter') {{
				p = p + geom_point(aes_for_geom_color)
			# }} else if (figtype == 'line') {{
			# 	p = p + geom_line(aes_for_geom)
			}} else if (figtype == 'bar') {{
				p = p + geom_bar(aes_for_geom) + xticks
			}} else if (figtype == 'col') {{
				p = p + geom_col(aes_for_geom) + xticks
			}} else if (figtype == 'pie') {{
				library(ggrepel)
				p = p + geom_col(aes_for_geom) + coord_polar("y", start=0) +
					theme_minimal() + geom_label_repel(
						aes_for_geom,
						y = cumsum(plotdata[,1]) - plotdata[,1]/2,
						label = paste0(unlist(round(plotdata[,1]/sum(plotdata[,1])*100,1)), '%'),
						show.legend= F) +
					theme(axis.title.x = element_blank(),
						axis.title.y = element_blank(),
						axis.text.y =element_blank())
			}} else if (figtype == 'violin') {{
				p = p + geom_violin(aes_for_geom) + xticks
			}} else if (figtype == 'boxplot') {{
				p = p + geom_boxplot(aes_for_geom) + xticks
			}} else if (figtype == 'histogram' || figtype == 'density') {{
				plotdata[,2] = as.factor(plotdata[,2])
				p = ggplot(plotdata, aes_string(x = bQuote(cnames[1])))
				params = list(alpha = .6)
				if (cnames[2] != '1') {{
					params$mapping = aes_string(fill = bQuote(cnames[2]))
				}}
				p = p + do.call(paste0("geom_", figtype), params)
			}} else if (figtype == 'freqpoly') {{
				plotdata[,2] = as.factor(plotdata[,2])
				p = ggplot(plotdata, aes_string(x = bQuote(cnames[1])))
				if (cnames[2] != '1') {{
					params$mapping = aes_string(color = bQuote(cnames[2]))
				}}
				p = p + do.call(paste0("geom_", figtype), params)
			}} else {{
				stop(paste('Unknown plot type:', figtype))
			}}
			{extrggs}
			print(p)
			dev.off()
		""".format(
			figtype = self.figtype,
			outprefix = self.outprefix,
			devpars = self.devpars,
			extrggs = ('p = p + ' + self.ggs) if self.ggs else ''
		)
		with open(self.outprefix + '.plot.R', 'w') as f:
			f.write(rcode)
		LOGGER.info("[{}] Running R code to plot ...".format(self.title))
		LOGGER.info("[{}] Data will be saved to: {}".format(self.title, self.outprefix + '.txt'))
		LOGGER.info("[{}] Plot will be saved to: {}".format(
			self.title, self.outprefix + '.' + self.figtype + '.png'))
		cmd = cmdy.Rscript(self.outprefix + '.plot.R', _exe = Rscript)
		if cmd.rc != 0:
			for line in cmd.stderr.splitlines():
				LOGGER.error("[{}] {}".format(self.title, line))