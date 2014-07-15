from datetime import date, timedelta

from django.db.models import Q
from django.contrib import admin
from django.contrib.admin import FieldListFilter, ListFilter, SimpleListFilter
from django.utils.translation import (
    ungettext,
    ugettext_lazy as _
)
from django.http import HttpResponse, HttpResponseRedirect

from djangofeeds import conf
from djangofeeds.models import (
    Feed, Post, Enclosure, Category,
    BlacklistedDomain,
    Article, NGram, PostNGram,
    ArticleByDomain,
)

from admin_steroids.options import BetterRawIdFieldsModelAdmin, ReadonlyModelAdmin
from admin_steroids.utils import get_admin_changelist_url, view_related_link, view_link
from admin_steroids.filters import NullListFilter

BaseModelAdmin = admin.ModelAdmin
BaseModelAdmin = BetterRawIdFieldsModelAdmin

class FreshStaleListFilter(SimpleListFilter):
    
    title = 'Freshness'
    
    parameter_name = 'freshness'
    
    default_value = None
    
    def __init__(self, request, params, model, model_admin):
        self.parameter_val = None
        try:
            self.parameter_val = request.GET.get(self.parameter_name, self.default_value)
            if self.parameter_val is not None:
                if self.parameter_val in (True, 'True', 1, '1'):
                    self.parameter_val = True
                else:
                    self.parameter_val = False
        except Exception, e:
            pass
        super(FreshStaleListFilter, self).__init__(request, params, model, model_admin)

    def lookups(self, request, model_admin):
        """
        Must be overriden to return a list of tuples (value, verbose value)
        """
        return [
            (None, _('All')),
            (True, _('Fresh')), # default
            (False, _('Stale')), # default
        ]

    def choices(self, cl):
        for lookup, title in self.lookup_choices:
            yield {
                'selected': self.parameter_val == lookup,
                'query_string': cl.get_query_string({
                    self.parameter_name: lookup,
                }, []),
                'display': title,
            }

    def queryset(self, request, queryset):
        """
        Returns the filtered queryset.
        """
        if self.parameter_val is True:
            # Only fresh.
            queryset = Feed.objects.get_fresh(qs=queryset)
        elif self.parameter_val is False:
            # Only stale.
            queryset = Feed.objects.get_stale(qs=queryset)
        return queryset

class FeedAdmin(BaseModelAdmin):
    """Admin for :class:`djangofeeds.models.Feed`."""
    
    list_display = (
        'name',
        'feed_url',
        'date_created',
        'date_last_refresh',
        'is_active',
        'fresh',
    )
    list_filter = (
        'is_active',
        FreshStaleListFilter,
    )
    search_fields = ['feed_url', 'name']
    
    readonly_fields = (
        'post_link',
        'fresh',
    )

    def lookup_allowed(self, *args, **kwargs):
        if conf.ALLOW_ADMIN_FEED_LOOKUPS:
            return True
        return super(FeedAdmin, self).lookup_allowed(*args, **kwargs)
    
    def post_link(self, obj=''):
        try:
            if not obj or not obj.id or not get_admin_changelist_url:
                return ''
            url = get_admin_changelist_url(Post) + ('?feed__id=%i' % obj.id)
            count = obj.post_set.all().count()
            return '<a href="%s" target="_blank"><input type="button" value="View %i" /></a>' % (url, count)
        except Exception, e:
            return str(e)
    post_link.short_description = 'Posts'
    post_link.allow_tags = True

class PostAdmin(BaseModelAdmin):
    """Admin for :class:`djangofeeds.models.Post`."""
    list_display = (
        'id',
        'feed',
        'title',
        'link',
        'author',
        'date_updated',
        'date_published',
        'has_article',
    )
    raw_id_fields = (
        'feed',
    )
    list_display_links = (
        'feed',
        'title',
    )
    list_filter = [
        'article_content_error_code',
        'article_content_success',
        'article_ngrams_extracted',
    ]
    search_fields = ['link', 'title']
    date_hierarchy = 'date_updated'
    
    readonly_fields = (
        'has_article',
        #'ngrams_link',
        'article_ngrams_extracted',
        'article_ngram_counts',
        'article_ngrams_extracted_datetime',
    )
    
    actions = (
        'reset_article_success',
    )
    
    def ngrams_link(self, obj=None):
        if not obj:
            return ''
        return view_related_link(obj, 'ngrams')
    ngrams_link.short_description = 'ngrams'
    ngrams_link.allow_tags = True
    
    def reset_article_success(self, request, queryset):
        queryset.update(article_content_success=None)
        return HttpResponseRedirect(request.META['HTTP_REFERER'])
    reset_article_success.short_description = 'Reset article content success flag on selected %(verbose_name_plural)s'
    
    def lookup_allowed(self, *args, **kwargs):
        if conf.ALLOW_ADMIN_FEED_LOOKUPS:
            return True
        return super(PostAdmin, self).lookup_allowed(*args, **kwargs)
    
    def has_article(self, obj=None):
        if not obj:
            return ''
        return bool(len((obj.article_content or '').strip()))
    has_article.boolean = True

class BlacklistedDomainAdmin(BaseModelAdmin):
    
    list_display = (
        'domain',
        'created',
    )
    
    search_fields = (
        'domain',
    )
    
    readonly_fields = (
        'created',
    )

class ArticleAdmin(ReadonlyModelAdmin):
    
    list_display = (
        'id',
        'year',
        'month',
        'total',
        'has_article',
        'ratio_extracted',
        'mean_length',
    )

class ArticleByDomainAdmin(ReadonlyModelAdmin):
    
    list_display = (
        'year',
        'month',
        'domain',
        'total',
        'missing',
        'missing_without_error',
        'missing_ratio',
        'missing_without_error_ratio',
    )
    
    def get_queryset(self, request):
        qs = super(ArticleByDomainAdmin, self).get_queryset(request)
        today = date.today()
        last_month = today - timedelta(days=30)
        qs = qs.filter(
            Q(year=today.year, month=today.month)|\
            Q(year=last_month.year, month=last_month.month))
        return qs
    
class NGramAdmin(BaseModelAdmin):
    
    list_display = (
        'text',
        'n',
    )
    
    list_filter = (
        'n',
    )
    
    search_fields = (
        'text',
    )
    
    readonly_fields = (
        'text',
        'n',
    )

class PostNGramAdmin(BaseModelAdmin):
    
    list_display = (
        'post',
        'ngram',
        'count',
    )
    
    search_fields = (
        'ngram__text',
    )
    
    readonly_fields = (
        'post',
        'post_link',
        'ngram',
        'count',
    )
    
    fields = (
        'post_link',
        'ngram',
        'count',
    )
    
    def post_link(self, obj=None):
        if not obj:
            return ''
        return view_link(obj.post)
    post_link.short_description = 'post'
    post_link.allow_tags = True
    
if NullListFilter:
    PostAdmin.list_filter.append(('article_content', NullListFilter))

admin.site.register(Category)
admin.site.register(Enclosure)
admin.site.register(Feed, FeedAdmin)
admin.site.register(Post, PostAdmin)
admin.site.register(BlacklistedDomain, BlacklistedDomainAdmin)
admin.site.register(Article, ArticleAdmin)
admin.site.register(ArticleByDomain, ArticleByDomainAdmin)

#admin.site.register(NGram, NGramAdmin)
#admin.site.register(PostNGram, PostNGramAdmin)
