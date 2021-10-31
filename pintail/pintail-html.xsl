<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
pintail - Build static sites from collections of Mallard documents
Copyright (c) 2015 Shaun McCance <shaunm@gnome.org>

This program is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns:str="http://exslt.org/strings"
                xmlns:exsl="http://exslt.org/common"
                xmlns:site="http://projectmallard.org/site/1.0/"
                xmlns:pintail="http://pintail.io/"
                xmlns="http://www.w3.org/1999/xhtml"
                extension-element-prefixes="exsl"
                exclude-result-prefixes="mal str exsl site pintail"
                version="1.0">

<xsl:param name="pintail.site.root" select="'/'"/>
<xsl:param name="pintail.site.dir"/>
<xsl:param name="pintail.format" select="'mallard'"/>

<xsl:param name="pintail.extension.link" select="$html.extension"/>

<xsl:param name="pintail.date"/>
<xsl:param name="pintail.time"/>

<!-- For backwards compatibility. Use pintail params instead. -->
<xsl:param name="mal.site.root" select="$pintail.site.root"/>
<xsl:param name="mal.site.dir" select="$pintail.site.dir"/>

<xsl:param name="mal.link.prefix"
           select="concat($pintail.site.root, substring($pintail.site.dir, 2))"/>

<xsl:param name="pintail.source.file"/>

<xsl:variable name="pintail.site.locale">
  <xsl:choose>
    <xsl:when test="$l10n.locale != ''">
      <xsl:value-of select="$l10n.locale"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:text>C</xsl:text>
    </xsl:otherwise>
  </xsl:choose>
</xsl:variable>

<xsl:param name="mal.link.default_root" select="concat($pintail.site.dir, 'index')"/>
<xsl:param name="html.css.root" select="$pintail.site.root"/>
<xsl:param name="html.js.root" select="$pintail.site.root"/>

<xsl:template name="pintail.site.sitetrail">
  <xsl:param name="page" select="."/>
  <xsl:param name="node" select="."/>
  <xsl:param name="xref" select="$node/@xref"/>
  <xsl:variable name="direction">
    <xsl:call-template name="l10n.direction">
      <xsl:with-param name="node" select="$page"/>
    </xsl:call-template>
  </xsl:variable>
  <xsl:variable name="xref_">
    <xsl:choose>
      <xsl:when test="$pintail.format = 'mallard'">
        <xsl:value-of select="$xref"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$pintail.site.dir"/>
        <xsl:text>index</xsl:text>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <xsl:variable name="sitetrail" select="str:tokenize($xref_, '/')[position() != last()]"/>
  <xsl:for-each select="$sitetrail">
    <xsl:variable name="pos" select="position()"/>
    <xsl:variable name="id">
      <xsl:for-each select="$sitetrail[position() &lt; $pos]">
        <xsl:text>/</xsl:text>
        <xsl:value-of select="."/>
      </xsl:for-each>
      <xsl:text>/index</xsl:text>
    </xsl:variable>
    <a class="trail">
      <xsl:attribute name="href">
        <xsl:call-template name="mal.link.target">
          <xsl:with-param name="xref" select="$id"/>
        </xsl:call-template>
      </xsl:attribute>
      <xsl:call-template name="mal.link.content">
        <xsl:with-param name="xref" select="$id"/>
        <xsl:with-param name="role" select="'guide'"/>
      </xsl:call-template>
    </a>
    <xsl:if test="$direction = 'rtl'">
      <xsl:text>&#x200F;</xsl:text>
    </xsl:if>
    <xsl:text>&#x00A0;» </xsl:text>
    <xsl:if test="$direction = 'rtl'">
      <xsl:text>&#x200F;</xsl:text>
    </xsl:if>
  </xsl:for-each>
</xsl:template>

<xsl:template name="mal2html.page.linktrails.empty">
  <xsl:param name="node" select="."/>
  <xsl:call-template name="html.linktrails.empty">
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
</xsl:template>

<xsl:template name="html.linktrails.empty">
  <xsl:param name="node" select="."/>
  <div class="trails">
    <div class="trail">
      <xsl:call-template name="pintail.site.sitetrail">
        <xsl:with-param name="page" select="$node"/>
        <xsl:with-param name="node" select="$node"/>
        <xsl:with-param name="xref">
          <xsl:value-of select="$pintail.site.dir"/>
          <xsl:value-of select="$node/@id"/>
        </xsl:with-param>
      </xsl:call-template>
    </div>
  </div>
</xsl:template>

<xsl:template name="mal2html.page.linktrails.trail.prefix">
  <xsl:param name="page" select="."/>
  <xsl:param name="node" select="."/>
  <xsl:call-template name="html.linktrails.prefix">
    <xsl:with-param name="page" select="$page"/>
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
</xsl:template>

<xsl:template name="html.linktrails.prefix">
  <xsl:param name="page" select="."/>
  <xsl:param name="node" select="."/>
  <xsl:call-template name="pintail.site.sitetrail">
    <xsl:with-param name="page" select="$page"/>
    <xsl:with-param name="node" select="$node"/>
  </xsl:call-template>
</xsl:template>

<xsl:template name="mal.link.target.extended">
  <xsl:param name="node" select="."/>
  <xsl:param name="xref" select="$node/@xref"/>
  <xsl:param name="href" select="$node/@href"/>
  <xsl:choose>
    <xsl:when test="contains($xref, '/')">
      <xsl:value-of select="$pintail.site.root"/>
      <xsl:if test="not(starts-with($xref, '/'))">
        <xsl:value-of select="substring($pintail.site.dir, 2)"/>
      </xsl:if>
      <xsl:variable name="pageid">
        <xsl:choose>
          <xsl:when test="contains($xref, '#')">
            <xsl:value-of select="substring-before($xref, '#')"/>
          </xsl:when>
          <xsl:otherwise>
            <xsl:value-of select="$xref"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:variable>
      <xsl:choose>
        <xsl:when test="starts-with($pageid, '/')">
          <xsl:value-of select="substring($pageid, 2)"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:value-of select="$pageid"/>
        </xsl:otherwise>
      </xsl:choose>
      <xsl:value-of select="$pintail.extension.link"/>
      <xsl:if test="contains($xref, '#')">
        <xsl:text>#</xsl:text>
        <xsl:value-of select="substring-after($xref, '#')"/>
      </xsl:if>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="$href"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template name="mal.link.linkid">
  <xsl:param name="node" select="."/>
  <xsl:choose>
    <xsl:when test="starts-with($node/@id, '/')">
      <xsl:value-of select="$node/@id"/>
    </xsl:when>
    <xsl:when test="contains($node/@id, '#')">
      <xsl:value-of select="$pintail.site.dir"/>
      <xsl:value-of select="$node/@id"/>
    </xsl:when>
    <xsl:when test="$node/self::mal:section">
      <xsl:value-of select="$pintail.site.dir"/>
      <xsl:value-of select="concat($node/ancestor::mal:page[1]/@id, '#', $node/@id)"/>
    </xsl:when>
    <xsl:otherwise>
      <xsl:value-of select="$pintail.site.dir"/>
      <xsl:value-of select="$node/@id"/>
    </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template name="mal.link.xref.linkid">
  <xsl:param name="node" select="."/>
  <xsl:param name="xref" select="$node/@xref"/>
  <xsl:variable name="linkid">
    <xsl:if test="starts-with($xref, '#')">
      <xsl:value-of select="$node/ancestor-or-self::mal:page/@id"/>
    </xsl:if>
    <xsl:value-of select="$xref"/>
  </xsl:variable>
  <xsl:if test="not(starts-with($linkid, '/'))">
    <xsl:value-of select="$pintail.site.dir"/>
  </xsl:if>
  <xsl:value-of select="$linkid"/>
</xsl:template>

<xsl:template name="mal2html.ui.links.img.src">
  <xsl:param name="node"/>
  <xsl:param name="thumb"/>
  <xsl:attribute name="src">
    <xsl:value-of select="$pintail.site.root"/>
    <xsl:choose>
      <xsl:when test="starts-with($thumb/@src, '/')">
        <xsl:value-of select="substring($thumb/@src, 2)"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of
            select="substring($thumb/ancestor-or-self::mal:page/@site:dir, 2)"/>
        <xsl:value-of select="$thumb/@src"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:attribute>
</xsl:template>

<xsl:template name="html.css">
  <xsl:param name="node" select="."/>
  <xsl:variable name="locale">
    <xsl:choose>
      <xsl:when test="$node/ancestor-or-self::*[@xml:lang]">
        <xsl:value-of select="$node/ancestor-or-self::*[@xml:lang][1]/@xml:lang"/>
      </xsl:when>
      <xsl:when test="$node/ancestor-or-self::*[@lang]">
        <xsl:value-of select="$node/ancestor-or-self::*[@lang][1]/@xml:lang"/>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$pintail.site.locale"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:variable>
  <link rel="stylesheet" type="text/css">
    <xsl:attribute name="href">
      <xsl:value-of select="$pintail.site.root"/>
      <xsl:text>pintail-</xsl:text>
      <xsl:value-of select="$pintail.format"/>
      <xsl:text>-</xsl:text>
      <xsl:value-of select="$locale"/>
      <xsl:text>.css</xsl:text>
    </xsl:attribute>
  </link>
</xsl:template>

<xsl:template name="html.js.script">
  <script type="text/javascript" src="{$html.js.root}yelp.js"/>
</xsl:template>

<xsl:template match="mal:links[@type = 'site-subdirs' or @type = 'site:subdirs']">
  <xsl:variable name="node" select="."/>
  <xsl:variable name="page" select="/mal:page"/>
  <xsl:variable name="links">
    <xsl:for-each select="$mal.cache/mal:page | $mal.cache/pintail:external">
      <xsl:if test="starts-with(@id, $pintail.site.dir)">
        <xsl:variable name="aft" select="substring-after(@id, $pintail.site.dir)"/>
        <xsl:if test="substring($aft, string-length($aft) - 5) = '/index'">
          <xsl:variable name="linklinkid">
            <xsl:call-template name="mal.link.linkid"/>
          </xsl:variable>
          <xsl:variable name="mid">
            <xsl:value-of select="substring($aft, 1, string-length($aft) - 6)"/>
          </xsl:variable>
          <xsl:if test="not(contains($mid, '/'))">
            <mal:link xref="{$linklinkid}">
              <mal:title type="sort">
                <xsl:choose>
                  <xsl:when test="mal:info/mal:title[@type = 'sort']">
                    <xsl:value-of select="normalize-space(mal:info/mal:title[@type = 'sort'][1])"/>
                  </xsl:when>
                  <xsl:otherwise>
                    <xsl:value-of select="normalize-space(mal:title[1])"/>
                  </xsl:otherwise>
                </xsl:choose>
              </mal:title>
            </mal:link>
          </xsl:if>
        </xsl:if>
      </xsl:if>
    </xsl:for-each>
  </xsl:variable>
  <xsl:variable name="nodes" select="exsl:node-set($links)/*"/>
  <xsl:variable name="role" select="@role"/>
  <xsl:if test="count($nodes) != 0">
    <div class="links subdirslinks">
      <xsl:apply-templates mode="mal2html.block.mode" select="mal:title"/>
      <ul>
        <xsl:for-each select="$nodes">
          <xsl:sort select="mal:title[@type = 'sort']"/>
          <xsl:call-template name="mal2html.links.ul.li">
            <xsl:with-param name="node" select="$node"/>
            <xsl:with-param name="xref" select="@xref"/>
            <xsl:with-param name="role" select="concat($role, ' site:subdirs guide')"/>
          </xsl:call-template>
        </xsl:for-each>
      </ul>
    </div>
  </xsl:if>
</xsl:template>

</xsl:stylesheet>
