<?xml version="1.0" encoding="utf-8"?>
<!-- $Id: docbook.xml,v 1.2 2006/01/30 00:25:11 tsunami Exp $ -->
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:xslthl="http://xslthl.sf.net"
                exclude-result-prefixes="xslthl"
                version="1.0">

<!-- Úpravy parametru -->

<xsl:param name="chunker.output.encoding" select="'UTF-8'"/>

<!-- Mají se pouzívat rozsírení -->
<xsl:param name="use.extensions" select="1"/>
<!-- Vypneme podporu pro rozsireni tabulek -->
<xsl:param name="tablecolumns.extension" select="0"/>

<!-- Mají se sekce automaticky číslovat -->
<xsl:param name="section.autolabel" select="1"/>

<!-- Mají císla sekcí obsahovat i císla kapitol -->
<xsl:param name="section.label.includes.component.label" select="1"/>

<!-- Mají se císlovat kapitoly -->
<xsl:param name="chapter.autolabel" select="1"/>

<!-- Pouzijeme námi definovaný CSS-->
<xsl:param name="html.stylesheet">docbook.css</xsl:param>
<xsl:param name="html.stylesheet.type">text/css</xsl:param>

<xsl:param name="generate.id.attributes" select="1"></xsl:param>
<xsl:param name="make.valid.html" select="1"></xsl:param>
<xsl:param name="autotoc.label.separator" select="'. '"></xsl:param>

<xsl:param name="highlight.source" select="1"></xsl:param>
<xsl:template match='xslthl:keyword' mode="xslthl">
 <b><xsl:apply-templates/></b>
</xsl:template>
<xsl:template match='xslthl:string' mode="xslthl">
 <span style="color: green"><xsl:apply-templates/></span>
</xsl:template>
<xsl:template match='xslthl:number' mode="xslthl">
 <span style="color: green"><xsl:apply-templates/></span>
</xsl:template>
<xsl:template match='xslthl:comment' mode="xslthl">
 <span style="color: gray"><xsl:apply-templates/></span>
</xsl:template>
<xsl:template match='xslthl:attribute' mode="xslthl">
 <span style="color: blue"><xsl:apply-templates/></span>
</xsl:template>
<xsl:template match='xslthl:value' mode="xslthl">
 <span style="color: purple"><xsl:apply-templates/></span>
</xsl:template>

<xsl:param name="generate.toc">
book      toc,title
</xsl:param>
</xsl:stylesheet>
