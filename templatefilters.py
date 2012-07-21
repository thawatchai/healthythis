import re

from google.appengine.api import users
from google.appengine.ext.webapp import template
from django.utils.html import *

import settings

register = template.create_template_register()

@register.filter
def create_login_url(dest):
    return users.create_login_url(dest)

@register.filter
def headbar(user):
    r = '<b><a href="/">Home</a></b>'
    if user:
        r = '<b>%s</b> &sdot; %s &sdot; <b><a href="/posts/new"><span class="hilight">Create a Post</span></a></b> &sdot; <b><a href="/posts/%s">My Posts</a></b> &sdot; <b><a href="%s">Log Out</a></b>' % \
                (user.email(), r, user.nickname(), users.create_logout_url('/'))
    else:
        r = '%s &sdot; <a href="%s"><b>Google Account Login</b></a>' % \
                (r, users.create_login_url('/'))
    return r

@register.filter
def show_post(post, user):
    if user and (post.user == user or user.email() in settings.EDITORS):
        info = '&nbsp;:: <a href="/posts/edit?key=%(key)s">edit</a>, <a href="/posts/delete?key=%(key)s">delete</a>' % {'key': post.key()}
    else:
        info = ''
    return """
<div class="post">
    %(content)s
	<p class="info">
        posted by <a href="/posts/%(user.nickname)s">%(user.nickname)s</a> at %(created_at)s :: <a href="/posts/view?key=%(key)s">permalink</a> %(info)s
	</p>
</div>""" % {
        'content': post.content,
        'user.nickname': post.user.nickname(),
        'created_at': show_time(post.created_at),
        'key': post.key(),
        'info': info,
        }

@register.filter
def pub_date(dt):
    return dt.strftime('%A, %d %B %Y %H:%M:%S GMT')

@register.filter
def show_date(dt):
    return dt.strftime('%B %d, %Y')

@register.filter
def show_time(dt):
    return dt.strftime('%H:%M')

@register.filter
def blank(s):
    return s if s else ''

@register.filter
def get_post_title(post):
    return post.title if post.title else '%s...' % strip_tags(post.content)[:30].strip()

