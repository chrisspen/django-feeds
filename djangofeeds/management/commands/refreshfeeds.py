from __future__ import with_statement

import sys
from optparse import make_option

from django.core.management.base import NoArgsCommand

from djangofeeds.tasks import refresh_feed
from djangofeeds.models import Feed
from djangofeeds.importers import FeedImporter


def print_feed_summary(feed_obj):
    """Dump a summary of the feed (how many posts etc.)."""
    posts = feed_obj.get_posts()
    enclosures_count = sum([post.enclosures.count() for post in posts])
    categories_count = sum([post.categories.count() for post in posts]) \
                        + feed_obj.categories.count()
    sys.stdout.write("*** Total %d posts, %d categories, %d enclosures\n" % \
            (len(posts), categories_count, enclosures_count))


def refresh_all(verbose=True, force=False):
    """ Refresh all feeds in the system. """
    importer = FeedImporter()
    for feed_obj in importer.feed_model.objects.all():
        sys.stdout.write(">>> Refreshing feed %s...\n" % \
                (feed_obj.name))
        feed_obj = importer.update_feed(feed_obj, force=force)

        if verbose:
            print_feed_summary(feed_obj)


def refresh_all_feeds_delayed(from_file=None):
    urls = (feed.feed_url for feed in Feed.objects.all())
    if from_file is not None:
        with file(from_file) as feedfile:
            urls = iter(feedfile.readlines())

    map(refresh_feed.delay, urls)


class Command(NoArgsCommand):
    option_list = NoArgsCommand.option_list + (
        make_option('--lazy', '-l',
                    action="store_true", dest="lazy", default=False,
                    help="Delay the actual importing to celery"),
        make_option('--file', '-f', action="store", dest="file",
                    help="Import all feeds from a file with feed URLs "
                    "seperated by newline."),
        make_option('--force', action="store_true", dest="force", default=False,
                    help="If given, will update feeds even if they're fresh."),
    )

    help = ("Refresh feeds", )

    requires_model_validation = True
    can_import_settings = True

    def handle_noargs(self, **options):
        lazy = options.get("lazy")
        from_file = options.get("file")
        force = options.get('force')
        if from_file or lazy:
            refresh_all_feeds_delayed(from_file)
        else:
            refresh_all(force=force)
