#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2009 Andris Reinman (http://www.turbinecms.com, http://www.andrisreinman.com)
#
# Permission is hereby granted, free of charge, to any person obtaining
#/ a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
# For details, see the TurbineCMS web site: http://www.turbinecms.com/

########################### IMPORT DECLARATIONS ###########################

# HTTP related 
import wsgiref.handlers
from google.appengine.ext import webapp

# Storage
from google.appengine.ext import db
from google.appengine.api import memcache

# Views
from google.appengine.ext.webapp import template
from django.template import Context, Template # for custom templates
from django.template.loader import render_to_string

# System
import os
import re

# Helpers
from django.utils import simplejson as json
import urllib
import logging


########################### DATABASE DEFINITIONS ###########################

# Setting table. Holds site-wide settings as name-value pairs
# as this information does not need to be indexed in any way, then most of the
# values can be json encoded strings (to hold more than one property in one row)

class Setting(db.Model):
  name = db.StringProperty()
  value = db.TextProperty()

# Page table holds page contents
class Page(db.Model):
  title = db.StringProperty()
  url = db.StringProperty() # clean url title like 'about' for 'About' etc.
  content = db.TextProperty()
  draft = db.BooleanProperty(default=True)
  owner = db.SelfReferenceProperty()
  created = db.DateTimeProperty(auto_now_add=True)
  edited = db.DateTimeProperty(auto_now=True)

########################### HELPER FUNCTIONS ###########################

# get_site_prefs()
# @return Array
# function retrieves site preferences as an array (title, description etc.)

def get_site_prefs():
  site_prefs= memcache.get("site-prefs")
  if site_prefs is not None:
    return site_prefs
  else:

    defaults = {
        'title': u'TurbineCMS',
        'description': u'TurbineCMS is a lightweight CMS designed to run on Google App Engine',
        'front': False,
        'templateDefault': True,
        'templateText': False
    }
    
    file = open('views/base.html')
    defaults['templateText'] = file.read()
    file.close()

    site_prefs = False
    query = db.GqlQuery("SELECT * FROM Setting WHERE name = :1", "site_prefs")
    for sp in query:
      try:
        site_prefs = sp.value and json.loads(sp.value) or defaults
      except:
        site_prefs = defaults
    if not site_prefs:
      site_prefs = defaults
      s = Setting()
      s.name = 'site_prefs'
      s.value = json.dumps(site_prefs)
      s.put()

    memcache.set("site-prefs", site_prefs)
    return site_prefs

# set_site_prefs()
# @param site_prefs Array
# function saves site preferences to database and memcache

def set_site_prefs(site_prefs):
  query = db.GqlQuery("SELECT * FROM Setting WHERE name = :1", "site_prefs")
  s = False
  for sp in query:
    try:
      s = sp
    except:
      s = False
  if not s:
    s = Setting()
  s.name = 'site_prefs'
  s.value = json.dumps(site_prefs)
  s.put()
  memcache.set("site-prefs", site_prefs)

# error_404()
# @param self Object
# function shows error 404 page

def error_404(self):
  self.response.set_status(404)
  
  site_prefs = get_site_prefs()
  
  template_values = {
    'site_title': site_prefs['title'],
    'description': site_prefs['description'],
    'title': u'Not Found',
    'content': u'The requested URL %s was not found on this server.' % self.request.path,
    'links': get_links()
  }
  
  try:
    if not site_prefs['templateDefault'] and len(site_prefs['templateText'].strip()):
      self.response.out.write(Template(site_prefs['templateText']).render(path, template_values))
      return
  except:
    pass
  path = os.path.join(os.path.dirname(__file__), 'views/base.html')
  self.response.out.write(template.render(path, template_values))


# get_page()
# @param url String
# @return db.Object
# function takes url identifier and retrieves corresponding row from the database

def get_page(url):
  page = memcache.get("page-%s" % url)
  if page is None:
    page = False
    query = db.GqlQuery("SELECT * FROM Page WHERE url = :1", url)
    for p in query:
      page = p
      memcache.set("page-%s" % url, page)
  return page

# get_unique_url()
# @param url String
# @return String
# function takes in an url and checks if it's already used.
# If the url already exists then adds a number to the end of the url

def get_unique_url(url):
  nr = 0
  t_url = url
  page = get_page(url)
  while page:
    nr += 1
    t_url = "%s-%s" % (url, nr)
    page = get_page(t_url)
  return t_url

# get_links()
# @return Array
# function retrieves alphabetically sorted list of active pages for the site menu

def get_links():
  links = memcache.get('site-links')
  if links is None:
    links = []
    site_prefs = get_site_prefs()
    query = Page.all()
    query.order("title")
    pages = query.fetch(1000)
    for page in pages:
      if not page.draft and not page.owner and (not site_prefs['front'] or site_prefs['front']!=page.url):
        links.append({'title':page.title,'url':page.url,'key':str(page.key())})

    memcache.set("site-links", links)
  return links


def smart_str(s, encoding='utf-8', strings_only=False, errors='strict'):
  """
  Returns a bytestring version of 's', encoded as specified in 'encoding'.
  If strings_only is True, don't convert (some) non-string-like objects.
  """
  if strings_only and isinstance(s, (types.NoneType, int)):
    return s
  if isinstance(s, str):
    return unicode(s).encode(encoding, errors)
  elif not isinstance(s, basestring):
    try:
      return str(s)
    except UnicodeEncodeError:
      if isinstance(s, Exception):
        # An Exception subclass containing non-ASCII data that doesn't
        # know how to print itself properly. We shouldn't raise a
        # further exception.
        return ' '.join([smart_str(arg, encoding, strings_only,
            errors) for arg in s])
      return unicode(s).encode(encoding, errors)
  elif isinstance(s, unicode):
    return s.encode(encoding, errors)
  elif s and encoding != 'utf-8':
    return s.decode('utf-8', errors).encode(encoding, errors)
  else:
    return s


########################### VIEW HANDLERS ###########################

# PageHandler
# Main handler, displays the frontpage and all other CMS pages

class PageHandler(webapp.RequestHandler):

  def get(self, url=False):
    
    #Load site prefs
    site_prefs = get_site_prefs()
    
    if not url and site_prefs['front']:
      url = site_prefs['front']
    
    # Load current page
    page = get_page(url)
    
    # Load subpages
    subpages = memcache.get('subpage-%s' % str(page.key()))
    if subpages is None:
      q = Page.all()
      q.filter("owner =", page)
      q.order("-created")
      subpages = q.fetch(1000)
      memcache.set('subpage-%s' % str(page.key()), subpages)
    
    if not page or page.draft:
      return error_404(self)

    #Render page
    template_values = {
        'site_title': site_prefs['title'],
        'description': site_prefs['description'],
        'title': page.title,
        'content': page.content,
        'subpages': subpages,
        'url': page.url,
        'links': get_links()
    }

    try:
      if not site_prefs.get('templateDefault',False) and site_prefs.get('templateText', False):
        t = Template(site_prefs['templateText'].encode('utf-8'))
        c = Context(template_values)
        tmpl = t.render(c)
        self.response.out.write(tmpl)
        return
    except:
      logging.debug('Template error')
      pass
    path = os.path.join(os.path.dirname(__file__), 'views/base.html')
    self.response.out.write(template.render(path, template_values))
      

# AdminMainHandler
# Main handler for the Admin section
# Displays all pages as a list

class AdminMainHandler(webapp.RequestHandler):
  def get(self):
    #Load site prefs
    site_prefs = get_site_prefs()
    
    q = Page.all()
    q.filter("owner =", None)
    q.order("title")
    pages = q.fetch(1000)
   
    #Render page
    template_values = {
        'site_title': site_prefs['title'],
        'description': site_prefs['description'],
        'pages': pages,
        'links': get_links(),
        'removed': self.request.get('removed') and True or False,
        'updated': self.request.get('updated') and True or False,
        'saved': self.request.get('saved') and self.request.get('saved') or False,
        'front':site_prefs['front'] or False
    }
    path = os.path.join(os.path.dirname(__file__), 'views/dashboard.html')
    self.response.out.write(template.render(path, template_values))

class AdminPublishHandler(webapp.RequestHandler):
  def get(self):
    key = self.request.get('key')
    try:
      page = Page.get(key)
    except:
      page = False
    if not page:
      return error_404()
    page.draft = False
    page.put()
    memcache.set("page-%s" % page.url, page)
    memcache.delete("site-links")
    self.redirect("/admin?published=%s" % key)

class AdminUnPublishHandler(webapp.RequestHandler):
  def get(self):
    key = self.request.get('key')
    try:
      page = Page.get(key)
    except:
      page = False
    if not page:
      return error_404()
    page.draft = True
    page.put()
    memcache.set("page-%s" % page.url, page)
    memcache.delete("site-links")
    self.redirect("/admin?unpublished=%s" % key)

class AdminRemoveHandler(webapp.RequestHandler):
  def get(self, url=False):
    if not url:
      return error_404()
    page = get_page(url);
    if not page:
      return error_404()
    if page.owner:
      memcache.delete('subpage-%s' % str(page.owner.key()))
      
    page.delete()
    memcache.delete("page-%s" % url)
    memcache.delete("site-links")
    self.redirect("/admin?removed=true")

class AdminEditHandler(webapp.RequestHandler):
  def get(self, url=False):
    #Load site prefs
    site_prefs = get_site_prefs()
    
    page = False
    #Load current page
    if url:
      page = get_page(url)
    
    #Render page
    template_values = {
        'site_title': site_prefs['title'],
        'description': site_prefs['description'],
        'url': url,
        'owner': page and page.owner and str(page.owner.key()) or False,
        'draft': not page or page.draft,
        'page': page,
        'front':page and site_prefs['front']==page.url or False,
        'links': get_links()
    }
    path = os.path.join(os.path.dirname(__file__), 'views/edit.html')
    self.response.out.write(template.render(path, template_values))
    
  def post(self):
    key = self.request.get('key')
    title = self.request.get('title')
    url = self.request.get('url')
    
    # Remove all non-ascii characters from the URL 
    p  = re.compile(r'[^a-z\-0-9]', re.IGNORECASE)
    url = p.sub('', url)
    
    content = self.request.get('content')
    on_front = self.request.get('front') and True or False
    draft = self.request.get('draft') and not on_front and True or False
    owner = self.request.get('owner') or False
    
    page = False
    if len(key):
      try:
        page = Page.get(key)
      except:
        page = False

    memcache.delete('site-links')
    
    if not page:
      page = Page()
      page.url = smart_str(get_unique_url(len(url) and url or u'page')) # url is set at the first save
    

    page.title = title
    page.content = content
    page.draft = draft
    
    if page.owner and page.owner!=owner:
      memcache.delete('subpage-%s' % str(page.owner.key()))
    
    page.owner = owner and db.Key(owner) or None
    
    if page.owner:
      memcache.delete('subpage-%s' % str(page.owner.key()))
        
    page.put()
    memcache.set("page-%s" % page.url, page)
    
    if on_front:
      # Set to front page
      site_prefs = get_site_prefs()
      if not site_prefs['front'] or site_prefs['front']!= page.url:
        site_prefs['front'] = page.url
        set_site_prefs(site_prefs)
        memcache.delete("site-links")
    
    self.redirect("/admin?saved=%s" % str(page.key()))

class AdminSiteHandler(webapp.RequestHandler):
  def get(self):
    #Load site prefs
    site_prefs = get_site_prefs()
    
    #Render page
    template_values = {
        'site_title': site_prefs['title'],
        'description': site_prefs['description'],
        'templateText': site_prefs['templateText'],
        'templateDefault': site_prefs['templateDefault'],
        'links': get_links()
    }
    path = os.path.join(os.path.dirname(__file__), 'views/site.html')
    self.response.out.write(template.render(path, template_values))
  def post(self):
    title = self.request.get('title')
    description = self.request.get('description')
    templateText = self.request.get('templateText')
    use_own_template = self.request.get('use_own_template') and True or False
    
    templateDefault = not use_own_template
    
    if not len(title):
      title = u'TurbineCMS'
      
    site_prefs = get_site_prefs()
    
    site_prefs['title'] = title
    site_prefs['description'] = description
    site_prefs['templateText'] = len(templateText) and templateText or False
    site_prefs['templateDefault'] = templateDefault
    
    set_site_prefs(site_prefs)
    
    self.redirect("/admin?updated=true")

def main():
  application = webapp.WSGIApplication([('/', PageHandler),
                                        (r'/page/(.*)', PageHandler),
                                        ('/admin', AdminMainHandler),
                                        ('/admin/add', AdminEditHandler),
                                        ('/admin/site', AdminSiteHandler),
                                        ('/admin/edit', AdminEditHandler),
                                        ('/admin/publish', AdminPublishHandler),
                                        ('/admin/unpublish', AdminUnPublishHandler),
                                        (r'/admin/edit/(.*)', AdminEditHandler),
                                        (r'/admin/remove/(.*)', AdminRemoveHandler)
                                        ],
                                       debug=True)
  wsgiref.handlers.CGIHandler().run(application)


if __name__ == '__main__':
  main()
