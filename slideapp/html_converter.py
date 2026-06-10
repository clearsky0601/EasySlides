import os
import re
import tempfile
import shutil
from functools import lru_cache

from django.conf import settings

from .models import Slide
from .src.converter import converter


# Bump when the rendering pipeline changes in a way that would invalidate
# previously cached HTML for unchanged Markdown (e.g. new directive support).
# v5: basetemp.html 加载 RevealNotes 插件（演讲者视图）
RENDER_VERSION = "5"


@lru_cache(maxsize=64)
def _convert_raw(version, content_hash, markdown_content):
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_md = os.path.join(temp_dir, 'temp.md')
        with open(temp_md, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        converter(temp_md)

        output_html = os.path.join(temp_dir, 'dist', 'index.html')
        with open(output_html, 'r', encoding='utf-8') as f:
            html = f.read()

        html = html.replace('./static/', '/static/')
        html = html.replace('./img/', '/static/img/')
        html = re.sub(r'<img(?![^>]*loading=)', '<img loading="lazy"', html)

        source_img_dir = os.path.join(temp_dir, 'dist', 'img')
        dest_img_dir = os.path.join(settings.BASE_DIR, 'static', 'img')
        if os.path.exists(source_img_dir):
            os.makedirs(dest_img_dir, exist_ok=True)
            for filename in os.listdir(source_img_dir):
                shutil.copy(os.path.join(source_img_dir, filename), dest_img_dir)

        return html


def convert_markdown(markdown_content):
    """Convert markdown to HTML with in-memory LRU cache. Raises on failure."""
    content_hash = Slide.compute_content_hash(markdown_content)
    return _convert_raw(RENDER_VERSION, content_hash, markdown_content)


def convert_and_cache(slide, markdown_content):
    """Convert markdown and persist the result on the Slide model. Raises on failure."""
    content_hash = Slide.compute_content_hash(markdown_content)
    cache_key = f"{RENDER_VERSION}:{content_hash}"
    if slide.content_hash == cache_key and slide.html_cache:
        return slide.html_cache

    html = _convert_raw(RENDER_VERSION, content_hash, markdown_content)
    Slide.objects.filter(id=slide.id).update(html_cache=html, content_hash=cache_key)
    return html
