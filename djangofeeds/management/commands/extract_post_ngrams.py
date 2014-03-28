from optparse import make_option

import warnings
#warnings.simplefilter('error', DeprecationWarning)

from django.core.management.base import BaseCommand

from djangofeeds.models import Post

class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
#        make_option('--feeds', dest="feeds", default='',
#                    help="Specific feeds to refresh."),
    )

    help = ("Extracts n-grams from the article text.", )

    def handle(self, *args, **options):
        Post.do_update()
        