from optparse import make_option

import warnings
#warnings.simplefilter('error', DeprecationWarning)

from django.core.management.base import BaseCommand

from djangofeeds.models import Post

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--posts',
            default='',
            help="Specific posts to refresh."),
        make_option(
            '--force',
            default=False,
            action='store_true',
            help="Generate, even if they have already been generated."),
    )

    help = ("Extracts n-grams from the article text.", )

    def handle(self, *args, **options):
        post_ids = map(int, [_ for _ in options['posts'].strip().split(',') if _.strip().isdigit()])
        Post.do_update(post_ids=post_ids, force=options['force'])
        