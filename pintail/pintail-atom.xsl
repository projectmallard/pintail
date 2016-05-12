<?xml version='1.0' encoding='UTF-8'?><!-- -*- indent-tabs-mode: nil -*- -->
<!--
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU Lesser General Public License as published by the Free
Software Foundation; either version 2 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
details.

You should have received a copy of the GNU Lesser General Public License
along with this program; see the file COPYING.LGPL.  If not, write to the
Free Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
02111-1307, USA.
-->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:mal="http://projectmallard.org/1.0/"
                xmlns:cache="http://projectmallard.org/cache/1.0/"
                xmlns:site="http://projectmallard.org/site/1.0/"
                xmlns:str="http://exslt.org/strings"
                xmlns:exsl="http://exslt.org/common"
                xmlns:html="http://www.w3.org/1999/xhtml"
                xmlns:atom="http://www.w3.org/2005/Atom"
                xmlns="http://www.w3.org/2005/Atom"
                extension-element-prefixes="exsl"
                exclude-result-prefixes="mal cache site html atom str exsl"
                version="1.0">

<xsl:import href="site2html.xsl"/>

<xsl:param name="feed.exclude_styles" select="''"/>

<xsl:template match="/">
  <feed>
    <!-- FIXME: possibly @site:dir starts-with $mal.site.dir? -->
    <!-- FIXME: exclude styles with multiple styles -->
    <xsl:for-each select="cache:cache/mal:page[
      (@site:dir = $mal.site.dir) and
      ($feed.exclude_styles = '' or
       not(contains(concat(' ', @style, ' '),
                    concat(' ', $feed.exclude_styles, ' ') )))
      ]">
      <xsl:sort select="mal:info/mal:revision[@date][last()]/@date"/>
      <xsl:apply-templates mode="site.atom.mode" select="."/>
    </xsl:for-each>
  </feed>
</xsl:template>

<xsl:template mode="site.atom.mode" match="mal:page">
  <entry>
    <!-- FIXME: mal2text on all inline content -->
    <!-- FIXME: look for @type=atom:title, @type=text, maybe <atom:title> -->
    <xsl:variable name="title">
      <xsl:choose>
        <xsl:when test="mal:info/atom:title">
          <xsl:apply-templates mode="mal2html.inline.mode"
                               select="mal:info/atom:title[1]/node()"/>
        </xsl:when>
        <xsl:when test="mal:info/mal:title[@type='atom:title']">
          <xsl:apply-templates mode="mal2html.inline.mode"
                               select="mal:info/mal:title[@type='atom:title'][1]/node()"/>
        </xsl:when>
        <xsl:when test="mal:info/mal:title[@type='text']">
          <xsl:apply-templates mode="mal2html.inline.mode"
                               select="mal:info/mal:title[@type='text'][1]/node()"/>
        </xsl:when>
        <xsl:otherwise>
          <xsl:apply-templates mode="mal2html.inline.mode"
                               select="mal:title/node()"/>
        </xsl:otherwise>
      </xsl:choose>
    </xsl:variable>
    <title>
      <xsl:value-of select="$title"/>
    </title>

    <xsl:if test="mal:info/atom:summary or mal:info/mal:desc">
      <xsl:variable name="summary">
        <xsl:choose>
          <xsl:when test="mal:info/atom:summary">
            <xsl:apply-templates mode="mal2html.inline.mode"
                                 select="mal:info/atom:summary[1]/node()"/>
          </xsl:when>
          <!-- FIXME: multiple descs in Mallard 1.1? -->
          <xsl:otherwise>
            <xsl:apply-templates mode="mal2html.inline.mode"
                                 select="mal:info/mal:desc[1]/node()"/>
          </xsl:otherwise>
        </xsl:choose>
      </xsl:variable>
      <summary>
        <xsl:value-of select="$summary"/>
      </summary>
    </xsl:if>

    <link>
      <xsl:attribute name="href">
        <xsl:call-template name="mal.link.target">
          <xsl:with-param name="xref" select="@id"/>
        </xsl:call-template>
      </xsl:attribute>
    </link>

<!-- FIXME -->
<!--
    <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
-->

    <updated>
      <xsl:value-of select="mal:info/mal:revision[@date][last()]/@date"/>
    </updated>

<!-- FIXME -->
<!--
    <content type="xhtml">
      <xsl:apply-templates mode="mal2html.block.mode"
                           select="document(@cache:href)/mal:page/mal:title/following-sibling::*/descendant-or-self::mal:p[1]"/>
    </content>
-->

<!-- FIXME -->
<!--
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml">
        <p>This is the entry content.</p>
      </div>
    </content>
-->
    <xsl:for-each select="mal:info/mal:credit
                            [contains(concat(' ', @type, ' '), ' author ')]">
      <author>
        <name>
          <xsl:value-of select="mal:name"/>
        </name>
        <xsl:if test="mal:email">
          <email>
            <xsl:value-of select="mal:email"/>
          </email>
        </xsl:if>
      </author>
    </xsl:for-each>
  </entry>
</xsl:template>

</xsl:stylesheet>
