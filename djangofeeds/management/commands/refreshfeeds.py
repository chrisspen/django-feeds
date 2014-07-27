from __future__ import with_statement

import sys
import time
from optparse import make_option
from datetime import datetime, timedelta
from multiprocessing import Process, Lock, cpu_count

import warnings
warnings.simplefilter('error', DeprecationWarning)

from django.core.management.base import NoArgsCommand
from django.db.models import Q
from django.db import connection, transaction
from django.utils import timezone

from joblib import Parallel, delayed

from djangofeeds.models import Feed
from djangofeeds.importers import FeedImporter

from chroniker.models import Job

def print_feed_summary(feed_obj):
    """Dump a summary of the feed (how many posts etc.)."""
    posts = feed_obj.get_posts()
    enclosures_count = sum([post.enclosures.count() for post in posts])
    categories_count = sum([post.categories.count() for post in posts]) \
                        + feed_obj.categories.count()
    sys.stdout.write("*** Total %d posts, %d categories, %d enclosures\n" % \
            (len(posts), categories_count, enclosures_count))

def get_feeds(importer, force=False, days=1, feed_ids=None, name_contains=None):
    if force:
        q = importer.feed_model.objects.all()
    else:
        q = importer.feed_model.objects.get_stale(days=days)
    if feed_ids:
        q = q.filter(id__in=feed_ids)
    q = q.filter(is_active=True)
    if name_contains:
        q = q.filter(name__icontains=name_contains)
    return q

#@transaction.commit_on_success
def refresh_feed_helper(feed_id):
    """
    Refreshes a specific feed.
    """
    print 'Refreshing feed %s...' % feed_id
    connection.close()
    importer = FeedImporter()
    feed = Feed.objects.get(id=feed_id)
    importer.update_feed(feed, force=True)

class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + (
        make_option('--force', action="store_true", dest="force", default=False,
                    help="If given, will update feeds even if they're fresh."),
        make_option('--days', dest="days", default=1,
                    help="The days to wait between consecutive refreshes."),
        make_option('--name_contains', dest="name_contains", default='',
                    help="Only refreshes feeds whose name contains this text."),
        make_option('--feeds', dest="feeds", default='',
                    help="Specific feeds to refresh."),
        make_option('--processes', default=0,
                    help="The number of processes to use."),
        make_option('--max-feeds', default=0,
                    help="The maximum number of feeds to refresh."),
        make_option('--dryrun', default=False, action='store_true',
                    help="If given, writes no changes."),
    )

    help = ("Refresh feeds", )

    requires_model_validation = True
    can_import_settings = True

    def handle_noargs(self, **options):
        
        # Initialize parameters.
        force = options.get('force')
        dryrun = options['dryrun']
        processes = int(options['processes']) or cpu_count()
        days = int(options['days'])
        feed_ids = [int(_.strip()) for _ in (options['feeds'] or '').split(',') if _.strip().isdigit()]
        name_contains = options['name_contains']
        max_feeds = int(options['max_feeds'])
        
        # Retrieve feeds.
        importer = FeedImporter()
        q = get_feeds(
            importer=importer,
            force=force,
            days=days,
            feed_ids=feed_ids,
            name_contains=name_contains,
        ).values_list('id', flat=True)
        if max_feeds:
            q = q[:max_feeds]
        total = q.count()
        print '%i feeds found' % total
        if dryrun:
            return
        
        # Initialize tasks.
        tasks = [
            delayed(refresh_feed_helper)(feed_id=feed_id)
            for feed_id in q.iterator()
        ]
        
        #TODO:launch thread to update Job progress?
        
        # Run all tasks.
        connection.close()
        Parallel(n_jobs=processes, verbose=50)(tasks)
        