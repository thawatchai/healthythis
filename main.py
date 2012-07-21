import os
import re
import logging # TODO: make use of logging

import wsgiref.handlers

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

template.register_template_library('templatefilters')

import settings


# Models *************************************************************

class Post(db.Model):
    user = db.UserProperty(required=True)
    byline = db.StringProperty(required=True)
    title = db.StringProperty()
    content = db.StringProperty(required=True)
    created_at = db.DateTimeProperty(auto_now_add=True)
    modified_at = db.DateTimeProperty(auto_now=True)


# Handlers ***********************************************************

RE_TAGS = re.compile('<\/(div|p|li)\>')

class ExtendedRequestHandler(webapp.RequestHandler):

    def __init__(self):
        self.template_path = '%s/templates' % os.path.join(os.path.dirname(__file__))
        self.values = {'current_user': users.get_current_user()}
        self.request_paths = None

    def response_render(self, filename, values={}):
        if not values:
            values = self.values
        self.response.out.write(template.render('%s/%s' % (self.template_path, filename), values))

    def get_page(self):
        try:
            return int(self.request.get('page', default_value=1))
        except:
            return 1

    def calculate_offset(self):
        return self.posts_per_page * self.get_page() - self.posts_per_page

    def get_cookie_and_clear(self, key):
        if self.request.cookies.has_key(key):
            self.response.headers.add_header('Set-Cookie', '%s=; path=/;' % key)
            return self.request.cookies[key]
        else:
            return None

    def get_note_and_notice(self):
        self.values['note'] = self.get_cookie_and_clear('note')
        self.values['notice'] = self.get_cookie_and_clear('notice')

    def set_cookie(self, k, v):
        self.response.headers.add_header('Set-Cookie', '%s="%s"; path=/;' % (k, v))

    def note(self, msg):
        self.values['note'] = '"%s"' % msg

    def save_note(self, msg):
        self.set_cookie('note', msg)

    def notice(self, msg):
        self.values['notice'] = '"%s"' % msg

    def save_notice(self, msg):
        self.set_cookie('notice', msg)

    def text2html(self, s):
        return s if RE_TAGS.search(s) else '<p>%s</p>' % s

    def get_request_path(self, i):
        if not self.request_paths:
            self.request_paths = self.request.path.split('/')
        return self.request_paths[i].replace('%40', '@') if len(self.request_paths) >= i+1 and self.request_paths[i] != '' else ''


class PostsPage(ExtendedRequestHandler):

    def __init__(self):
        ExtendedRequestHandler.__init__(self)
        self.posts_per_page = 20

    def get_post_from_param(self):
        key = self.request.get('key')
        try:
            self.values['post'] = Post.get(key)
        except:
            self.values['post'] = None

    def get_owned_post_from_param(self):
        if self.values['current_user']:
            self.get_post_from_param()
            if self.values['post'] and self.values['post'].user != self.values['current_user']:
                if self.values['user'].email() not in settings.EDITORS:
                    self.values['post'] = None
        else:
            self.values['post'] = None

    def specify_custom_format(self, s, format):
        return True if len(s) > 4 and s[-4:] == '.%s' % format else False


class PostsListPage(PostsPage):

    def get(self):
        self.get_note_and_notice()

        self.values['byline'] = self.get_request_path(2)
        if self.specify_custom_format(self.values['byline'], 'rss'):
            self.values['byline'] = self.values['byline'][:-4]

        if self.values['byline']:
            q = Post.gql('WHERE byline = :1 ORDER BY created_at DESC', self.values['byline'])
        else:
            q = Post.gql('ORDER BY created_at DESC')

        self.values.update({
            'posts': q.fetch(self.posts_per_page, self.calculate_offset()),
            'has_older_posts': self.__has_older_posts(q),
            'page': self.get_page(),
            })

        if self.specify_custom_format(self.request.path, 'rss'):
            self.response_render('posts_list.rss.xml')
        else:
            self.response_render('posts_list.html')

    def __has_older_posts(self, q):
        expected = self.get_page() * self.posts_per_page + 1
        if q.count(expected) == expected:
            return True
        else:
            return False


class PostsViewPage(PostsPage):

    def get(self):
        self.get_note_and_notice()
        self.get_post_from_param()
        if self.values['post']:
            self.response_render('posts_view.html')
        else:
            self.redirect('/posts')


class PostsNewPage(PostsPage):
    
    def get(self):
        if self.values['current_user']:
            self.values['enable_editor'] = True
            self.response_render('posts_edit.html')
        else:
            self.redirect(users.create_login_url('/posts/new'))

    def post(self):
        if not self.values['current_user']:
            self.redirect(users.create_login_url('/posts/new'))
        else:
            post_text = self.request.get('post_text')
            post_title = self.request.get('post_title')
            if not post_text:
                self.notice('Please enter the post content.')
                self.response_render('posts_edit.html')
            else:
                post = Post(
                        user=self.values['current_user'],
                        byline=self.values['current_user'].nickname(),
                        content=self.text2html(post_text),
                        title=post_title
                        )
                post.put()
                self.save_note('The post has been submitted.')
                self.redirect('/posts')


class PostsEditPage(PostsPage):

    def __error(self):
        self.save_notice('The post with the specified key does not exist, or you are not allowed to edit it.')
        self.redirect('/error')

    def get(self):
        self.get_owned_post_from_param()
        if self.values['post']:
            self.values['enable_editor'] = True
            self.response_render('posts_edit.html')
        else:
            self.__error()

    def post(self):
        self.get_owned_post_from_param()
        if self.values['post']:
            post_text = self.request.get('post_text')
            post_title = self.request.get('post_title')
            if post_text:
                self.values['post'].content = self.text2html(post_text)
                self.values['post'].title = post_title
                self.values['post'].put()
                self.save_note('The post has been edited.')
                self.redirect('/posts/view?key=%s' % self.values['post'].key())
            else:
                self.notice('The post content cannot be blank. The content is restored.')
                self.response_render('posts_edit.html')
        else:
            self.__error()


class PostsDeletePage(PostsPage):

    def __error(self):
        self.save_notice('The post with the specified key does not exist, or you are not allowed to delete it.')
        self.redirect('/error')

    def get(self):
        self.get_owned_post_from_param()
        if self.values['post']:
            self.response_render('posts_delete.html')
        else:
            self.__error()

    def post(self):
        self.get_owned_post_from_param()
        if self.values['post']:
            if self.request.get('yes') == 'Yes':
                self.values['post'].delete()
                self.save_note('The post has been deleted.')
            self.redirect('/posts')
        else:
            self.__error()


class HomeRedirectPage(webapp.RequestHandler):

    def get(self):
        self.redirect('/posts')


class ErrorPage(ExtendedRequestHandler):

    def get(self):
        self.get_note_and_notice()
        self.response.set_status(404)
        self.response_render('error.html')


# Main ***************************************************************

def main():
    app = webapp.WSGIApplication([

        ('/posts/view', PostsViewPage),
        ('/posts/new', PostsNewPage),
        ('/posts/edit', PostsEditPage),
        ('/posts/delete', PostsDeletePage),
        ('/posts.*', PostsListPage),
        ('/', HomeRedirectPage),
        ('/.*', ErrorPage),
        ],
        debug=True)
    wsgiref.handlers.CGIHandler().run(app)

if __name__ == '__main__':
    main()

