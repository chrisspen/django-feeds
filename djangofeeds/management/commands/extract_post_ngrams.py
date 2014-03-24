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

from chroniker.models import Job

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
#        make_option('--feeds', dest="feeds", default='',
#                    help="Specific feeds to refresh."),
        #make_option('--force', action='store_true', default=False),
    )

    help = ("Attempts to extract the article text from the URL associated with each post.", )

    def handle(self, *args, **options):
        q = Post.objects.all_ngramless()
        total = q.count()
        i = 0
        print '%i total records.' % (total,)
        for post in q.iterator():
            i += 1
            print '\r%i of %i %.2f%%' % (i, total, i/float(total)*100),
            post.extract_ngrams()
            #break