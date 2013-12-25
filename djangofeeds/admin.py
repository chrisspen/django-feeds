from django.contrib import admin
from djangofeeds import conf

from djangofeeds.models import Feed, Post, Enclosure, Category

NullListFilter = None
BetterRawIdFieldsModelAdmin = None
try:
    from admin_steroids import BetterRawIdFieldsModelAdmin
    from admin_steroids.utils import get_admin_changelist_url
    from admin_steroids.filters import NullListFilter
except ImportError:
    get_admin_changelist_url = None

BaseModelAdmin = admin.ModelAdmin
if BetterRawIdFieldsModelAdmin:
    BaseModelAdmin = BetterRawIdFieldsModelAdmin

class FeedAdmin(BaseModelAdmin):
    """Admin for :class:`djangofeeds.models.Feed`."""
    list_display = (
        'name',
        'feed_url',
        'date_last_refresh',
        'is_active',
        'date_created',
    )
    search_fields = ['feed_url', 'name']
    
    readonly_fields = (
        'post_link',
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
    ]
    search_fields = ['link', 'title']
    date_hierarchy = 'date_updated'
    
    readonly_fields = (
        'has_article',
    )

    def lookup_allowed(self, *args, **kwargs):
        if conf.ALLOW_ADMIN_FEED_LOOKUPS:
            return True
        return super(PostAdmin, self).lookup_allowed(*args, **kwargs)
    
    def has_article(self, obj=None):
        if not obj:
            return ''
        return bool(len((obj.article_content or '').strip()))
    has_article.boolean = True

if NullListFilter:
    PostAdmin.list_filter.append(('article_content', NullListFilter))

admin.site.register(Category)
admin.site.register(Enclosure)
admin.site.register(Feed, FeedAdmin)
admin.site.register(Post, PostAdmin)
