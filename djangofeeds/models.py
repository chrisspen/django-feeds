"""Model working with Feeds and Posts."""
import sys
import re
import gc
import httplib as http
from datetime import datetime, timedelta
from django.utils.timezone import utc
from collections import defaultdict

from django.conf import settings
from django.db import models, reset_queries
from django.db.models import signals
from django.db.transaction import commit_on_success
from django.utils.translation import ugettext_lazy as _
from django.utils.encoding import force_text
from django.utils import timezone

from picklefield.fields import PickledObjectField

from nltk.util import ngrams as ngrams_iter

from fake_useragent import UserAgent
ua = UserAgent()

import hashlib
md5_constructor = hashlib.md5

try:
    from admin_steroids.utils import StringWithTitle
    APP_LABEL = StringWithTitle('djangofeeds', 'Feeds')
except ImportError:
    APP_LABEL = 'djangofeeds'

from djangofeeds import conf
from djangofeeds.utils import naturaldate
from djangofeeds.managers import FeedManager, PostManager
from djangofeeds.managers import EnclosureManager, CategoryManager
from djangofeeds.backends import backend_or_default

ACCEPTED_STATUSES = frozenset([http.OK,
                               http.FOUND,
                               http.NOT_MODIFIED,
                               http.MOVED_PERMANENTLY,
                               http.TEMPORARY_REDIRECT])

FEED_TIMEDOUT_ERROR = "TIMEDOUT_ERROR"
FEED_NOT_FOUND_ERROR = "NOT_FOUND_ERROR"
FEED_GENERIC_ERROR = "GENERIC_ERROR"

FEED_TIMEDOUT_ERROR_TEXT = _(
    u"The feed does not seem to be respond. We will try again later.")
FEED_NOT_FOUND_ERROR_TEXT = _(
    u"You entered an incorrect URL or the feed you requested does not exist "
    u"anymore.")
FEED_GENERIC_ERROR_TEXT = _(
    u"There was a problem with the feed you provided, please check the URL "
    u"for mispellings or try again later.")

FEED_ERROR_CHOICES = (
        (FEED_TIMEDOUT_ERROR, FEED_TIMEDOUT_ERROR_TEXT),
        (FEED_NOT_FOUND_ERROR, FEED_NOT_FOUND_ERROR_TEXT),
        (FEED_GENERIC_ERROR, FEED_GENERIC_ERROR_TEXT),
)


def timedelta_seconds(delta):
    """Convert :class:`datetime.timedelta` to seconds.

    Doesn't account for negative values.

    """
    return max(delta.total_seconds(), 0)


class Category(models.Model):
    """Category associated with :class:`Post`` or :class:`Feed`.

    .. attribute:: name

        Name of the category.

    .. attribute:: domain

        The type of category

    """
    name = models.CharField(_(u"name"), max_length=128)
    domain = models.CharField(_(u"domain"),
                              max_length=128, null=True, blank=True)

    objects = CategoryManager()

    class Meta:
        app_label = APP_LABEL
        unique_together = ("name", "domain")
        verbose_name = _(u"category")
        verbose_name_plural = _(u"categories")

    def __unicode__(self):
        if self.domain:
            return u"%s [%s]" % (self.name, self.domain)
        return u"%s" % self.name


class Feed(models.Model):
    """An RSS feed

    .. attribute:: name

        The name of the feed.

    .. attribute:: feed_url

        The URL the feed is located at.

    .. attribute:: description

        The feeds description in full text/HTML.

    .. attribute:: link

        The link the feed says it's located at.
        Can be different from :attr:`feed_url` as it's the
        source we got from the user.

    .. attribute:: date_last_refresh

        Date of the last time this feed was refreshed.

    .. attribute:: last_error

        The last error message (if any).

    .. attribute:: ratio

        The apparent importance of this feed.

    """
    supports_categories = False
    supports_enclosures = False

    name = models.CharField(_(u"name"), max_length=200)
    feed_url = models.URLField(_(u"feed URL"), unique=True)
    description = models.TextField(_(u"description"))
    link = models.URLField(_(u"link"), max_length=200, blank=True)
    http_etag = models.CharField(_(u"E-Tag"),
                                 editable=False, blank=True,
                                 null=True, max_length=200)
    http_last_modified = models.DateTimeField(_(u"Last-Modified"), null=True,
                                              editable=False, blank=True)
    date_last_refresh = models.DateTimeField(_(u"date of last refresh"),
                                        null=True, blank=True, editable=False)
    categories = models.ManyToManyField(Category)
    last_error = models.CharField(_(u"last error"), blank=True, default="",
                                 max_length=32, choices=FEED_ERROR_CHOICES)
    ratio = models.FloatField(default=0.0)
    sort = models.SmallIntegerField(_(u"sort order"), default=0)
    date_created = models.DateTimeField(_(u"date created"), auto_now_add=True, default=timezone.now)
    date_changed = models.DateTimeField(_(u"date changed"), auto_now=True, default=timezone.now)
    
    # this date is used to know if the feed is still used by some
    # real users. Update the value when the user use the feed.
    date_last_requested = models.DateTimeField(
        _(u"last requested"),
        auto_now_add=True)
    
    summary_detail_link_regex = models.CharField(
        max_length=1000,
        blank=True,
        null=True,
        help_text=_('''A regular expression to extra the link from the
            entry\'s summary detail section. This is useful when the entry\'s
            main link is a wrapper but the summary contains the true URL.'''))
    
    is_active = models.BooleanField(_(u"is active"), default=True)
    
    freq = models.IntegerField(
        _(u"frequency"),
        default=conf.REFRESH_EVERY)

    objects = FeedManager()

    class Meta:
        app_label = APP_LABEL
        ordering = ("id", )
        verbose_name = _(u"syndication feed")
        verbose_name_plural = _(u"syndication feeds")

    def __init__(self, *args, **kwargs):
        super(Feed, self).__init__(*args, **kwargs)
        self.poststore = backend_or_default()

    def natural_key(self):
        return (self.feed_url,)
    natural_key.dependencies = []

    def __unicode__(self):
        return u"%s (%s)" % (self.name, self.feed_url)

    def fresh(self):
        return type(self).objects.get_fresh().filter(id=self.id).exists()
    fresh.boolean = True

    def get_posts(self, **kwargs):
        """Get all :class:`Post`s for this :class:`Feed` in order."""
        return self.poststore.all_posts_by_order(self)

    def get_post_count(self):
        return self.poststore.get_post_count(self)

    def frequencies(self, limit=None, order="-date_updated"):
        posts = self.post_set.values("date_updated").order_by(order)[0:limit]
        return [posts[i - 1]["date_updated"] - post["date_updated"]
                    for i, post in enumerate(posts)
                        if i]

    def average_frequency(self, limit=None, min=5,
            default=timedelta(hours=2)):
        freqs = self.frequencies(limit=limit)
        if len(freqs) < min:
            return default
        average = sum(map(timedelta_seconds, freqs)) / len(freqs)
        return timedelta(seconds=average)

    def update_frequency(self, limit=None, min=5, save=True):
        self.freq = timedelta_seconds(self.average_frequency(limit, min))
        save and self.save()

    def expire_old_posts(self, min_posts=30, max_posts=120, commit=False):
        """Expire old posts.

        :keyword min_posts: Minimum number of post by feed.

        :keyword max_posts: The maximum number of posts to keep for a feed.
            We keep this value high to avoid incessant delete on feed that
            have a bit more than the `min_posts` value.
        :keyword commit: Commit the transaction, set to ``False`` if you want
            to manually handle the transaction.

        :returns: The number of messages deleted.

        """
        by_date = self.post_set.order_by("-date_published")
        if len(by_date) > max_posts:
            expired_posts = [post["id"]
                                for post in by_date.values("id")[min_posts:]]
            Post.objects.filter(pk__in=expired_posts).delete()
            return len(expired_posts)
        return 0

    def is_error_status(self, status):
        return status == http.NOT_FOUND or status not in ACCEPTED_STATUSES

    def error_for_status(self, status):
        if status == http.NOT_FOUND:
            return FEED_NOT_FOUND_ERROR
        if status not in ACCEPTED_STATUSES:
            return FEED_GENERIC_ERROR

    def save_error(self, error_msg):
        self._set_last_error = True
        self.last_error = error_msg
        self.save()
        return self

    def save_generic_error(self):
        return self.save_error(FEED_GENERIC_ERROR)

    def save_timeout_error(self):
        return self.save_error(FEED_TIMEDOUT_ERROR)

    def set_error_status(self, status):
        return self.save_error(self.error_for_status(status))

    @property
    def date_last_refresh_naturaldate(self):
        return unicode(naturaldate(self.date_last_refresh))


def sig_reset_last_error(sender, instance, **kwargs):
    if not instance._set_last_error:
        instance.last_error = u""
signals.pre_save.connect(sig_reset_last_error, sender=Feed)


def sig_init_feed_set_last_error(sender, instance, **kwargs):
    instance._set_last_error = False
signals.post_init.connect(sig_init_feed_set_last_error, sender=Feed)


class Enclosure(models.Model):
    """Media enclosure for a Post

    .. attribute:: url

        The location of the media attachment.

    .. attribute:: type

        The mime/type of the attachment.

    .. attribute:: length

        The actual content length of the file
        pointed to at :attr:`url`.

    """
    url = models.URLField(_(u"URL"))
    type = models.CharField(_(u"type"), max_length=200)
    length = models.PositiveIntegerField(_(u"length"), default=0)

    objects = EnclosureManager()

    class Meta:
        app_label = APP_LABEL
        verbose_name = _(u"enclosure")
        verbose_name_plural = _(u"enclosures")

    def __unicode__(self):
        return u"%s %s (%d)" % (self.url, self.type, self.length)

from chroniker.models import Job
from django_materialized_views.models import MaterializedView, parse_stripe

class Post(models.Model, MaterializedView):
    """A Post for an RSS feed

    .. attribute:: feed

        The feed which this is a post for.

    .. attribute:: title

        The title of the post.

    .. attribute:: link

        Link to the original article.

    .. attribute:: content

        The posts content in full-text/HTML.

    .. attribute:: guid

        The GUID for this post (unique for :class:`Feed`)

    .. attribute:: author

        Name of this posts author.

    .. attribute:: date_published

        The date this post was published.

    .. attribute:: date_updated

        The date this post was last changed/updated.

    .. attribute:: enclosures

        List of media attachments for this post.

    """

    feed = models.ForeignKey(Feed, null=False, blank=False)
    title = models.CharField(_(u"title"), max_length=1000)
    # using 2048 for long URLs, only work for MySQL 5.0.3 +
    link = models.URLField(_(u"link"), max_length=2048)
    content = models.TextField(
        _(u"content"),
        blank=True,
        null=True)
    
    article_content = models.TextField(
        _(u"article content"),
        blank=True,
        null=True,
        help_text=_('''The full article content retrieved from the URL.'''))
    
    article_content_length = models.PositiveIntegerField(
        blank=True,
        null=True,
        editable=False,
        db_index=True)
    
    article_content_error_code = models.CharField(
        max_length=25,
        blank=True,
        null=True,
        db_index=True,
        help_text=_('Any HTTP error code received while attempting to download the article.'))
    
    article_content_error_reason = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text=_('Any HTTP error reason received while attempting to download the article.'))
    
    article_content_success = models.NullBooleanField(default=None, db_index=True)
    
    article_content_error = models.TextField(blank=True, null=True)
    
    article_ngrams_extracted = models.BooleanField(
        default=False,
        editable=False,
        db_index=True)
    
    article_ngrams_extracted_datetime = models.DateTimeField(
        blank=True,
        null=True,
        editable=False,
        db_index=True)
    
    article_ngram_counts = PickledObjectField(
        blank=True,
        null=True,
        compress=True,
        help_text=_('{ngram:count}'))
    
    guid = models.CharField(_(u"guid"), max_length=200, blank=True)
    author = models.CharField(_(u"author"), max_length=50, blank=True)
    date_published = models.DateField(_(u"date published"))
    date_updated = models.DateTimeField(_(u"date updated"))
    enclosures = models.ManyToManyField(Enclosure, blank=True)
    categories = models.ManyToManyField(Category)

    objects = PostManager()

    class Meta:
        app_label = APP_LABEL
        # sorting on anything else than id is catastrophic for
        # performance
        # even an ordering by id is not smart
        # ordering = ["-id"]
        verbose_name = _(u"post")
        verbose_name_plural = _(u"posts")

    def auto_guid(self):
        """Automatically generate a new guid from the metadata available."""
        return md5_constructor("|".join((
                    self.title, self.link, self.author))).hexdigest()

    def __unicode__(self):
        return u"%s" % self.title

    def save(self, *args, **kwargs):
        
        old = None
        if self.id:
            old = type(self).objects.get(id=self.id)
        
        self.article_content = (self.article_content or '').strip()
        if self.article_content:
            self.article_content = force_text(self.article_content, errors='replace')
        else:
            self.article_content = None
        self.article_content_length = len((self.article_content or '').strip())
        
        if old and old.article_content != self.article_content:
            self.article_ngrams_extracted = False
        
#        self.article_content_success = bool((self.article_content or '').strip())
#        if self.article_content_success:
#            self.article_content_error = None
            
        super(Post, self).save(*args, **kwargs)

    @property
    def date_published_naturaldate(self):
        date = self.date_published
        as_datetime = datetime(date.year, date.month, date.day, tzinfo=utc)
        return unicode(naturaldate(as_datetime))

    @property
    def date_updated_naturaldate(self):
        return unicode(naturaldate(self.date_updated))
    
    def retrieve_article_content(self, force=False):
        import webarticle2text
        if self.article_content and not force:
            return
        self.article_content = webarticle2text.extractFromURL(
            self.link,
            only_mime_types=conf.GET_ARTICLE_CONTENT_ONLY_MIME_TYPES,
            ignore_robotstxt=True,
            userAgent=ua.random)
        self.article_content_error_code = None
        self.article_content_error_reason = None
        self.article_content_success = bool((self.article_content or '').strip())
        self.article_content_error = None
        self.save()
    
    @classmethod
    def needs_update(cls, *args, **kwargs):
        return bool(Post.objects.all_ngramless().only('id').exists())
    
    stripable = True
    
    @classmethod
    def do_update(cls, stripe=None, print_status=None, post_ids=None, force=False, *args, **kwargs):
        tmp_debug = settings.DEBUG
        settings.DEBUG = False
        print_status = print_status or (lambda message, count=0, total=0: sys.stdout.write(message+'\n'))
        try:
            stripe_num, stripe_mod = parse_stripe(stripe)
            if force:
                q = Post.objects.all_ngramable()
            else:
                q = Post.objects.all_ngramless()
            q = q.only('id')
            if post_ids:
                q = q.filter(id__in=post_ids)
            if stripe is not None:
                # Note, we need to escape modulo operator twice since QuerySet does
                # additional parameter interpolation.
                q = q.extra(where=['((id %%%% %i) = %i)' % (stripe_mod, stripe_num)])
            total = q.count()
            i = 0
            print_status('%i total records.' % (total,))
            for post in q.iterator():
                i += 1
                #print '\r%i of %i %.2f%%' % (i, total, i/float(total)*100),
                message = '%i of %i %.2f%%' % (i, total, i/float(total)*100)
                print_status(message=message, total=total, count=i)
                post.extract_ngrams(force=force)
                reset_queries()
                gc.collect()
        finally:
            settings.DEBUG = tmp_debug
    
    @commit_on_success
    def extract_ngrams(self, force=False):
        if not force and (self.article_ngrams_extracted or not self.article_content_length):
            return
        
        #self.ngrams.all().delete()
        
        min_text_length = 4
        min_n = 1
        max_n = 6
        
        content = (self.content or '') + ' ' + (self.article_content or '')
        
        text = content.strip().lower()
        text = re.sub(r'[^a-zA-Z0-9]+', ' ', text, flags=re.DOTALL)
        text = re.sub(r'[\s\t\n\r]+', ' ', text, flags=re.DOTALL)
        text = text.strip()
        text = text.split(' ')
        
        ngrams = []
        for n in xrange(min_n, max_n+1):
            ngrams.extend(ngrams_iter(sequence=text, n=n))
        #print '%i ngrams' % len(ngrams)
        #ngram_counts = defaultdict(int)
        ngram_counts = {}
#        new_ngram_objects = []
#        new_ngrams = set()
        for ngram in ngrams:
            ngram = (' '.join(ngram)).strip()
            if len(ngram) < min_text_length:
                continue
            ngram_counts.setdefault(ngram, 0)
            ngram_counts[ngram] += 1
#            if ngram not in new_ngrams and not NGram.objects.filter(text=ngram).exists():
#                new_ngrams.add(ngram)
#                new_ngram_objects.append(NGram(text=ngram, n=ngram.count(' ')+1))
        
#        NGram.objects.bulk_create(new_ngram_objects)
#        PostNGram.objects.bulk_create([
#            PostNGram(post=self, ngram=NGram.objects.get(text=ngram), count=count)
#            for ngram, count in ngram_counts.iteritems()
#        ])
        
        self.article_ngram_counts = ngram_counts
        self.article_ngrams_extracted = True
        self.article_ngrams_extracted_datetime = datetime.now()
        self.save()

    @classmethod
    @commit_on_success
    def clear_ngrams(cls, post_ids=None, force=False):
        q = cls.objects.filter(article_ngrams_extracted = True).only('id')
        if post_ids:
            q = q.filter(id__in=post_ids)
        total = q.count()
        i = 0
        for self in q.iterator():
            i += 1
            if i == 1 or not i % 100 or i == total:
                print '\rClearing ngrams %i of %i %.02f%%.' % (i, total, float(i)/total*100),
                sys.stdout.flush()
            self.article_ngram_counts = None
            self.article_ngrams_extracted = False
            self.article_ngrams_extracted_datetime = None
            self.save()

class NGram(models.Model):
    
    text = models.CharField(
        max_length=1000,
        blank=False,
        null=False,
        unique=True,
        editable=False,
        db_index=True)
    
    n = models.PositiveIntegerField(
        blank=False,
        null=False,
        editable=False,
        db_index=True)
    
    def __unicode__(self):
        return self.text
    
    def save(self, *args, **kwargs):
        
        self.text = (self.text or '').strip().lower()
        
        self.n = self.text.count(' ') + 1
        
        super(NGram, self).save(*args, **kwargs)

class PostNGram(models.Model):
    """
    Links an n-gram to a specific post.
    """
    
    post = models.ForeignKey('Post', related_name='ngrams', editable=False)
    
    ngram = models.ForeignKey('NGram', related_name='posts', editable=False)
    
    count = models.PositiveIntegerField(
        blank=False,
        null=False,
        editable=False,
        db_index=True)
    
    class Meta:
        unique_together = (
            ('post', 'ngram'),
        )

class BlacklistedDomain(models.Model):
    
    domain = models.CharField(
        max_length=150,
        blank=False,
        null=False,
        db_index=True,
        help_text=_('All URLs with this domain will be ignored and not imported.'))
    
    created = models.DateTimeField(
        auto_now_add=True,
        null=True,
        editable=False,
        blank=True)
    
    class Meta:
        app_label = APP_LABEL
        ordering = ('domain',)
    
    def __unicode__(self):
        return self.domain
    
    @classmethod
    def is_blacklisted(cls, url):
        """
        Returns true if the given URL matches a blacklisted domain.
        Returns false otherwise.
        """
        from urlparse import urlparse
        url = (url or '').strip()
        if not url:
            return False
        netloc = urlparse(url).netloc
        domain2 = '.'.join(netloc.split('.')[-2:])
        domain3 = '.'.join(netloc.split('.')[-3:])
        if cls.objects.filter(domain=domain2).count():
            return True
        elif cls.objects.filter(domain=domain3).count():
            return True
        return False

class Article(models.Model):
    
    # MySQL can have no more than 255 length...
    id = models.CharField(max_length=255, primary_key=True)
    
    year = models.PositiveIntegerField(editable=False)
    
    month = models.PositiveIntegerField(editable=False)
    
    total = models.PositiveIntegerField(editable=False)
    
    has_article = models.PositiveIntegerField(editable=False)
    
    mean_length = models.PositiveIntegerField(editable=False)
    
    ratio_extracted = models.FloatField(editable=False)
    
    class Meta:
        managed = False
        #db_table = 'database_size_table'
        #db_table = 'database_size_databasesizetable'
        ordering = ('-year', '-month')
        app_label = APP_LABEL
        verbose_name = _('article')
        