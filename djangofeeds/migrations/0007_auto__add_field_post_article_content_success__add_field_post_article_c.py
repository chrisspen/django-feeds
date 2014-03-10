# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Adding field 'Post.article_content_success'
        db.add_column(u'djangofeeds_post', 'article_content_success',
                      self.gf('django.db.models.fields.NullBooleanField')(default=None, null=True, blank=True),
                      keep_default=False)

        # Adding field 'Post.article_content_error'
        db.add_column(u'djangofeeds_post', 'article_content_error',
                      self.gf('django.db.models.fields.TextField')(null=True, blank=True),
                      keep_default=False)


    def backwards(self, orm):
        # Deleting field 'Post.article_content_success'
        db.delete_column(u'djangofeeds_post', 'article_content_success')

        # Deleting field 'Post.article_content_error'
        db.delete_column(u'djangofeeds_post', 'article_content_error')


    models = {
        'djangofeeds.article': {
            'Meta': {'ordering': "('-year', '-month')", 'object_name': 'Article', 'managed': 'False'},
            'has_article': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'id': ('django.db.models.fields.CharField', [], {'max_length': '255', 'primary_key': 'True'}),
            'month': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'ratio_extracted': ('django.db.models.fields.FloatField', [], {}),
            'total': ('django.db.models.fields.PositiveIntegerField', [], {}),
            'year': ('django.db.models.fields.PositiveIntegerField', [], {})
        },
        'djangofeeds.blacklisteddomain': {
            'Meta': {'ordering': "('domain',)", 'object_name': 'BlacklistedDomain'},
            'created': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'null': 'True', 'blank': 'True'}),
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '150', 'db_index': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'})
        },
        'djangofeeds.category': {
            'Meta': {'unique_together': "(('name', 'domain'),)", 'object_name': 'Category'},
            'domain': ('django.db.models.fields.CharField', [], {'max_length': '128', 'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '128'})
        },
        'djangofeeds.enclosure': {
            'Meta': {'object_name': 'Enclosure'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'length': ('django.db.models.fields.PositiveIntegerField', [], {'default': '0'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'url': ('django.db.models.fields.URLField', [], {'max_length': '200'})
        },
        'djangofeeds.feed': {
            'Meta': {'ordering': "('id',)", 'object_name': 'Feed'},
            'categories': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['djangofeeds.Category']", 'symmetrical': 'False'}),
            'date_changed': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now': 'True', 'blank': 'True'}),
            'date_created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.now', 'auto_now_add': 'True', 'blank': 'True'}),
            'date_last_refresh': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            'date_last_requested': ('django.db.models.fields.DateTimeField', [], {'auto_now_add': 'True', 'blank': 'True'}),
            'description': ('django.db.models.fields.TextField', [], {}),
            'feed_url': ('django.db.models.fields.URLField', [], {'unique': 'True', 'max_length': '200'}),
            'freq': ('django.db.models.fields.IntegerField', [], {'default': '10800'}),
            'http_etag': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'http_last_modified': ('django.db.models.fields.DateTimeField', [], {'null': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'is_active': ('django.db.models.fields.BooleanField', [], {'default': 'True'}),
            'last_error': ('django.db.models.fields.CharField', [], {'default': "''", 'max_length': '32', 'blank': 'True'}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '200', 'blank': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '200'}),
            'ratio': ('django.db.models.fields.FloatField', [], {'default': '0.0'}),
            'sort': ('django.db.models.fields.SmallIntegerField', [], {'default': '0'}),
            'summary_detail_link_regex': ('django.db.models.fields.CharField', [], {'max_length': '1000', 'null': 'True', 'blank': 'True'})
        },
        'djangofeeds.post': {
            'Meta': {'object_name': 'Post'},
            'article_content': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'article_content_error': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'article_content_error_code': ('django.db.models.fields.CharField', [], {'db_index': 'True', 'max_length': '25', 'null': 'True', 'blank': 'True'}),
            'article_content_error_reason': ('django.db.models.fields.CharField', [], {'max_length': '200', 'null': 'True', 'blank': 'True'}),
            'article_content_success': ('django.db.models.fields.NullBooleanField', [], {'default': 'None', 'null': 'True', 'blank': 'True'}),
            'author': ('django.db.models.fields.CharField', [], {'max_length': '50', 'blank': 'True'}),
            'categories': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['djangofeeds.Category']", 'symmetrical': 'False'}),
            'content': ('django.db.models.fields.TextField', [], {'null': 'True', 'blank': 'True'}),
            'date_published': ('django.db.models.fields.DateField', [], {}),
            'date_updated': ('django.db.models.fields.DateTimeField', [], {}),
            'enclosures': ('django.db.models.fields.related.ManyToManyField', [], {'to': "orm['djangofeeds.Enclosure']", 'symmetrical': 'False', 'blank': 'True'}),
            'feed': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['djangofeeds.Feed']"}),
            'guid': ('django.db.models.fields.CharField', [], {'max_length': '200', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'link': ('django.db.models.fields.URLField', [], {'max_length': '2048'}),
            'title': ('django.db.models.fields.CharField', [], {'max_length': '1000'})
        }
    }

    complete_apps = ['djangofeeds']