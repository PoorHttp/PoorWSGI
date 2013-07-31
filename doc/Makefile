all: single

book: clean dokumentace.xml xhtml-chunk.xsl xhtml-common.xsl
	#xsltproc -o html-cs/ xhtml-chunk.xsl dokumentace.xml
	#xsltproc -o html-en/ xhtml-chunk.xsl documentation.xml
	( cd html-cs; \
            java -cp "/usr/share/java/saxon.jar:/usr/share/java/xslthl.jar" \
            -Dxslthl.config=file:///usr/share/xml/docbook/stylesheet/docbook-xsl/highlighting/xslthl-config.xml \
            com.icl.saxon.StyleSheet -o /dev/null ../dokumentace.xml ../xhtml-chunk.xsl )

single: clean dokumentace.xml xhtml-onechunk.xsl xhtml-common.xsl
	xsltproc -o html-cs/ xhtml-onechunk.xsl dokumentace.xml
	xsltproc -o html-en/ xhtml-onechunk.xsl documentation.xml

fo: dokumentace.xml
	xsltproc -o dokumentace.fo fo-common.xsl dokumentace.xml

rtf: dokumentace.xml
	docbook2rtf dokumentace.xml

pdf: dokumentace.fo
	fop dokumentace.fo -pdf dokumentace.pdf

ps: dokumentace.xml
	docbook2ps dokumentace.xml

clean:
	@rm -f html/*.html
	@rm -f dokumentace.aux dokumentace.dvi dokumentace.log dokumentace.out
	@rm -f dokumentace.rtf dokumentace.tex dokumentace.ps dokumentace.pdf dokumentace.fo
