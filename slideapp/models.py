# slideapp/models.py

import hashlib
from django.db import models
from django.contrib.auth.models import User


class SlideCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('position', 'name')

    def __str__(self):
        return self.name


class Slide(models.Model):
    title = models.CharField(max_length=200, default='未命名')
    content = models.TextField(blank=True)
    category = models.CharField(max_length=100, blank=True, default='')
    category_ref = models.ForeignKey(
        SlideCategory,
        null=True,
        blank=True,
        related_name='slides',
        on_delete=models.SET_NULL,
    )
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    lock = models.BooleanField(default=True)
    version = models.IntegerField(default=0)
    html_cache = models.TextField(blank=True, default='')
    content_hash = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ('sort_order', '-updated_at', '-id')

    @staticmethod
    def compute_content_hash(content):
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def extract_title_from_content(self):
        lines = self.content.split('\n')
        in_front_matter = False
        for line in lines:
            stripped_line = line.strip()
            if stripped_line in ('---', '+++'):
                in_front_matter = not in_front_matter
                continue
            if in_front_matter:
                continue
            if stripped_line.startswith('#'):
                return stripped_line.lstrip('#').strip()
        return '未命名幻灯片'
