from __future__ import with_statement

import sys
import time
from optparse import make_option
from datetime import datetime, timedelta
from multiprocessing import Process, Lock

import warnings
warnings.simplefilter('error', DeprecationWarning)

from django.core.management.base import NoArgsCommand
from django.db.models import Q
from django.db import connection
from django.utils import timezone

from djangofeeds.models import Feed
from djangofeeds.importers import FeedImporter

try:
    from chroniker.models import Job
except ImportError:
    Job = None

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

def refresh_all(lock, verbose=True, force=False, days=1, name_contains=None, feed_ids=None, first=False):
    """ Refresh all feeds in the system. """
    importer = FeedImporter()
    
    total = None
    last_total = None
    i = 0
    while 1:
    
        # Retrieve the next stale feed.
        feed = None
        try:
            lock.acquire()
            q = get_feeds(
                importer=importer,
                force=force,
                days=days,
                feed_ids=feed_ids,
                name_contains=name_contains,
            )
            if first:
                if total is None:
                    total = q.count()
                if last_total is not None:
                    i = total - last_total
                last_total = total
            if q.exists():
                feed = q[0]
                feed.date_last_refresh = timezone.now()
                feed.save()
                print "Refreshing feed %s..." % (feed.name,)
            else:
                print 'Nothing left to evaluate.'
                return
        finally:
            lock.release()
    
        # Update status.
        if first and Job:
            if feed:
                Job.update_progress(total_parts=total, total_parts_complete=i)
            else:
                Job.update_progress(total_parts=total, total_parts_complete=total)
                return
        
        # Update feed.
        feed = importer.update_feed(feed, force=True)

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
        make_option('--processes', default=4,
                    help="The number of processes to use."),
    )

    help = ("Refresh feeds", )

    requires_model_validation = True
    can_import_settings = True

    def handle_noargs(self, **options):
        force = options.get('force')
        processes = int(options['processes'])
        feed_ids = [int(_.strip()) for _ in (options['feeds'] or '').split(',') if _.strip().isdigit()]
        process_stack = []
        lock = Lock()
        if processes:
            # Start processes.
            for _ in xrange(processes):
                connection.close()
                p = Process(
                    target=refresh_all,
                    kwargs=dict(
                        lock=lock,
                        feed_ids=feed_ids,
                        force=force,
                        days=int(options['days']),
                        name_contains=options['name_contains'],
                        first=not _,
                ))
                #p.daemon = True#breaks evaluate() launching processes of its own
                p.start()
                process_stack.append(p)
            # Wait for processes to end.
            while any(p for p in process_stack if p.is_alive()):
                time.sleep(1)
