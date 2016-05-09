# pintail - Build static sites from collections of Mallard documents
# Copyright (c) 2016 Shaun McCance <shaunm@gnome.org>
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; see the file COPYING.LGPL.  If not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.

import urllib
import uuid

import pintail.search

import elasticsearch

class ElasticSearchProvider(pintail.search.SearchProvider):
    analyzers = {
        'ar': 'arabic',
        'bg': 'bulgarian',
        'ca': 'catalan',
        'ckb': 'sorani',
        'cs': 'czech',
        'da': 'danish',
        'de': 'german',
        'el': 'greek',
        'en': 'english',
        'es': 'spanish',
        'eu': 'basque',
        'fa': 'persian',
        'fi': 'finnish',
        'fr': 'french',
        'ga': 'irish',
        'gl': 'galician',
        'hi': 'hindi',
        'hu': 'hungarian',
        'hy': 'armenian',
        'id': 'indonesian',
        'it': 'italian',
        'ja': 'cjk',
        'ko': 'cjk',
        'lt': 'lithuanian',
        'lv': 'latvian',
        'nb': 'norwegian',
        'nl': 'dutch',
        'nn': 'norwegian',
        'no': 'norwegian',
        'pt': 'portuguese',
        'pt-br': 'brazilian',
        'ro': 'romanian',
        'ru': 'russian',
        'sv': 'swedish',
        'th': 'thai',
        'tr': 'turkish',
        'zh': 'cjk',
    }

    def __init__(self, site):
        pintail.search.SearchProvider.__init__(self, site)
        self.epoch = str(uuid.uuid1())
        elhost = self.site.config.get('search_elastic_host')
        self.elastic = elasticsearch.Elasticsearch([elhost])
        self._indexes = []

    def get_analyzer(self, lang):
        # FIXME: if POSIX code, convert to BCP47
        if lang.lower() in ElasticSearchProvider.analyzers:
            return ElasticSearchProvider.analyzers[lang.lower()]
        if '-' in lang:
            return ElasticSearchProvider.get_analyzer(lang[:lang.rindex('-')])
        return 'english'

    def create_index(self, lang):
        if lang in self._indexes:
            return
        self._indexes.append(lang)

        analyzer = self.get_analyzer(lang)
        self.elastic.indices.create(
            index=(self.epoch + '@' + lang),
            body={
                'mappings': {
                    'page': {
                        'properties': {
                            'path': {'type': 'string', 'index': 'not_analyzed'},
                            'lang': {'type': 'string', 'index': 'not_analyzed'},
                            'domain': {'type': 'string', 'index': 'not_analyzed'},
                            'title': {'type': 'string', 'analyzer': analyzer},
                            'desc': {'type': 'string', 'analyzer': analyzer},
                            'keywords': {'type': 'string', 'analyzer': analyzer},
                            'content': {'type': 'string', 'analyzer': analyzer}
                        }
                    }
                }
            })

    def index_page(self, page):
        self.site.log('INDEX', page.site_id)

        lang = 'en'
        self.create_index(lang)

        title = page.get_title()
        desc = page.get_desc()
        keywords = page.get_keywords()
        content = page.get_content()

        elid = urllib.parse.quote(page.site_id, safe='')
        elindex = self.epoch + '@' + lang

        domains = []
        for domain in page.directory.get_search_domains():
            if isinstance(domain, list):
                if domain[0] == page.page_id:
                    domains.append(domain[1])
            else:
                domains.append(domain)

        self.elastic.index(index=elindex, doc_type='page', id=elid, body={
            'path': page.site_id,
            'lang': lang,
            'domain': domains,
            'title': title,
            'desc': desc,
            'keywords': keywords,
            'content': content
        })
