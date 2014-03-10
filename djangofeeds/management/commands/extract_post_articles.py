from __future__ import with_statement

import sys
import urllib2
from optparse import make_option
from datetime import datetime, timedelta
import traceback
from StringIO import StringIO

import warnings
#warnings.simplefilter('error', DeprecationWarning)

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from djangofeeds.models import Feed, Post
from djangofeeds.importers import FeedImporter

try:
    from chroniker.models import Job
except ImportError:
    Job = None

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
#        make_option('--feeds', dest="feeds", default='',
#                    help="Specific feeds to refresh."),
        make_option('--force', action='store_true', default=False,
                    help="Specific feeds to refresh."),
        make_option('--year', 
                    help="A specific year to process."),
        make_option('--month', 
                    help="A specific month to process."),
    )

    help = ("Attempts to extract the article text from the URL associated with each post.", )

    def handle(self, *args, **options):
        q = Post.objects.all_articleless()
        q = q.filter(article_content_error_code__isnull=True)
        q = q.filter(article_content_success__isnull=True)
        #TODO:retry article_content_success=False but with error_code__isnull=False?
        year = options['year']
        month = options['month']
        if year:
            q = q.filter(date_published__year=year)
        if month:
            q = q.filter(date_published__month=month)
        #q = q.only('id', )
        q = q.order_by('-date_published')
        total = q.count()
        i = 0
        success_count = 0 # successfully retrieved non-empty content
        error_count = 0 # any type of exception was thrown
        meh_count = 0 # no errors were thrown, even if we didn't get content
        print '%i posts without an article.' % (total,)
        for post in q.iterator():
            i += 1
            print '\rProcessing post %i (%i of %i, %i success, %i errors, %i mehs)...' \
                % (post.id, i, total, success_count, error_count, meh_count),
            sys.stdout.flush()
            try:
                post.retrieve_article_content(force=options['force'])
                success_count += bool(len((post.article_content or '').strip()))
                meh_count += not bool(len((post.article_content or '').strip()))
            except urllib2.HTTPError, e:
                error_count += 1
                print>>sys.stderr
                print>>sys.stderr, 'Error: Unable to retrieve %s: %s' % (post.link, e)
                post.article_content_error_code = e.code
                post.article_content_error_reason = e.reason
                post.article_content_success = False
                post.save()
            except Exception, e:
                post.article_content_success = False
                ferr = StringIO()
                traceback.print_exc(file=ferr)
                post.article_content = None
                post.article_content_error = ferr.getvalue()
                post.save()
                error_count += 1
                print>>sys.stderr
                print>>sys.stderr, 'Error: Unable to retrieve %s: %s' % (post.link, e)
        print
        print '-'*80
        print '%i successes' % success_count
        print '%i errors' % error_count
        