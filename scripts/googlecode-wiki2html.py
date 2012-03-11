#!/usr/bin/env python2

# Google Code wiki downloader script
# Copyright (C) 2011  Vyacheslav Levit
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys
import urllib2
import re
from HTMLParser import HTMLParser


URL = "http://code.google.com/p/%(project)s/wiki/%(wikipage)s?show=content"
CONTENT_TYPE = ("""<meta http-equiv="Content-Type" content="text/html;"""
               """ charset=UTF-8" />""")


class WikiParser(HTMLParser):

    divno = 0
    enddiv = None
    startdiv = None
    startheadend = None

    def handle_starttag(self, tag, attrs):
        if tag == 'div' and self.enddiv is None:
            if self.startdiv is None:
                self.startdiv = self.getpos()
            self.divno += 1
        elif tag == 'head' and self.startheadend is None:
            self.startheadend = self.getpos()
            offset = self.startheadend[1] + len(self.get_starttag_text())
            self.startheadend = (self.startheadend[0], offset)

    def handle_endtag(self, tag):
        if tag == 'div' and self.startdiv is not None:
            self.divno -= 1
            if self.divno == 0:
                self.enddiv = self.getpos()


def page_cleanup(data, project):
    parser = WikiParser()
    parser.feed(data)
    lines = data.splitlines()
    headline, offset = parser.startheadend
    lines[headline - 1] = (lines[headline - 1][:offset] +
                           '\n %s' % CONTENT_TYPE +
                           lines[headline - 1][offset:])
    endline, offset = parser.enddiv
    lines = lines[:endline]
    lines[-1] = lines[-1][:offset] + "</div>\n\n\n </body>\n</html>"
    data = '\n'.join(lines)
    data = re.sub(r'(<a\s+href=)"/p/%s/wiki/([^"]*)">' % project,
                  r'\1"\2.html">', data)
    return data


def usage():
    print 'Usage: googlecode-wiki2html project wikipage [wikipage.html]'


def main():
    if sys.argv[1] in ('-h', '--help'):
        usage()
        sys.exit(0)
    elif len(sys.argv) < 3:
        usage()
        sys.exit(1)
    project = sys.argv[1]
    wikipage = sys.argv[2]
    htmlfile = sys.argv[3] if len(sys.argv) > 2 else '%s.html' % wikipage
    f = urllib2.urlopen(URL % {'project': project, 'wikipage': wikipage})
    data = f.read()
    data = page_cleanup(data, project)
    f = open(htmlfile, 'w')
    f.write(data)
    f.close()
    exit(0)


if __name__ == '__main__':
    main()
