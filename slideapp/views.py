import json
import os
import sqlite3
import traceback
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.db import connections, transaction
from django.db.models import Max, Prefetch
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Slide, SlideCategory
from .html_converter import convert_and_cache

BASE_DIR = Path(settings.BASE_DIR).resolve()
DEFAULT_DB_NAME = 'db.sqlite3'
REQUIRED_MANAGEMENT_COLUMNS = {
    'id', 'title', 'content', 'created_at', 'updated_at', 'lock', 'version',
    'category', 'category_ref_id', 'sort_order', 'html_cache', 'content_hash',
    'deleted_at',
}


def active_slides():
    """未进回收站的幻灯片；所有列表/详情查询统一从这里出发。"""
    return Slide.objects.filter(deleted_at__isnull=True)


def display_db_name(path):
    path = Path(path)
    try:
        return str(path.resolve().relative_to(BASE_DIR))
    except ValueError:
        return path.name


def discover_db_paths():
    found = []
    seen = set()
    for directory in (BASE_DIR, BASE_DIR / 'archive'):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob('*.sqlite3')):
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            found.append(resolved)

    def sort_key(path):
        is_default = path.name == DEFAULT_DB_NAME and path.parent == BASE_DIR
        return (0 if is_default else 1, str(path))

    return sorted(found, key=sort_key)


def db_compatibility(path):
    try:
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        slide_cols = {
            row['name']
            for row in conn.execute('PRAGMA table_info(slideapp_slide)').fetchall()
        }
        if not REQUIRED_MANAGEMENT_COLUMNS.issubset(slide_cols):
            if slide_cols and REQUIRED_MANAGEMENT_COLUMNS - slide_cols == {'deleted_at'}:
                return False, '需迁移（SLIDES_DB=<路径> manage.py migrate --database=slides slideapp）'
            return False, '旧版结构'
        category_table = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ('slideapp_slidecategory',),
        ).fetchone()
        if not category_table:
            return False, '缺少分类表'
        return True, ''
    except sqlite3.Error:
        return False, '无法读取'
    finally:
        try:
            conn.close()
        except UnboundLocalError:
            pass


def db_slide_count(path):
    try:
        with sqlite3.connect(path) as conn:
            row = conn.execute('SELECT COUNT(*) FROM slideapp_slide').fetchone()
        return row[0] if row else 0
    except sqlite3.Error:
        return 0


def current_db_path():
    return Path(settings.DATABASES['slides']['NAME']).resolve()


def database_options():
    current = current_db_path()
    options = []
    for path in discover_db_paths():
        compatible, reason = db_compatibility(path)
        options.append({
            'path': str(path),
            'name': display_db_name(path),
            'count': db_slide_count(path) if compatible else None,
            'compatible': compatible,
            'reason': reason,
            'active': path == current,
        })
    return options


def apply_database(path):
    resolved = str(Path(path).resolve())
    os.environ['SLIDES_DB'] = resolved
    settings.DATABASES['slides']['NAME'] = resolved
    connections['slides'].settings_dict['NAME'] = resolved
    connections['slides'].close()


# 上传图片限制：白名单内的位图格式（不含 svg，避免内嵌脚本），单文件 10MB
ALLOWED_IMAGE_TYPES = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'image/webp': '.webp',
}
MAX_IMAGE_SIZE = 10 * 1024 * 1024


@login_required
def upload_image(request):
    if request.method == 'POST':
        image = request.FILES.get('image')
        if image and image.content_type in ALLOWED_IMAGE_TYPES:
            if image.size > MAX_IMAGE_SIZE:
                return JsonResponse({'error': '图片超过 10MB 限制'}, status=400)
            # 扩展名由白名单映射生成（不信任原文件名），uuid 防冲突
            ext = ALLOWED_IMAGE_TYPES[image.content_type]
            filename = uuid.uuid4().hex + ext
            filepath = os.path.join(settings.MEDIA_ROOT, 'uploads', filename)

            # 确保上传目录存在
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            # 保存文件
            with open(filepath, 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)

            # 返回图片的访问 URL
            url = settings.MEDIA_URL + 'uploads/' + filename
            return JsonResponse({'url': url})
        else:
            return JsonResponse(
                {'error': '不支持的图片格式（仅限 png/jpg/gif/webp）'}, status=400)
    else:
        return JsonResponse({'error': '不支持的请求方法'}, status=405)





# slideapp/views.py
SORT_OPTIONS = {
    'manual': ('sort_order', '-updated_at', '-id'),
    'updated_desc': ('-updated_at', '-id'),
    'updated_asc': ('updated_at', 'id'),
    'created_desc': ('-created_at', '-id'),
    'created_asc': ('created_at', 'id'),
}


def get_sort(request):
    sort = request.GET.get('sort', 'manual')
    if sort not in SORT_OPTIONS:
        sort = 'manual'
    return sort


def get_slide_categories(slide_ordering, slide_filter=None):
    qs = active_slides()
    if slide_filter:
        qs = qs.filter(**slide_filter)
    qs = qs.order_by(*slide_ordering)
    return (
        SlideCategory.objects
        .prefetch_related(Prefetch('slides', queryset=qs, to_attr='prefetched_slides'))
        .order_by('position', 'name')
    )


@login_required
def index(request):
    sort = get_sort(request)
    slide_ordering = SORT_OPTIONS[sort]
    categories = list(get_slide_categories(slide_ordering))
    uncategorized_slides = list(
        active_slides().filter(category_ref__isnull=True).order_by(*slide_ordering)
    )
    category_sections = [
        {
            'id': category.id,
            'name': category.name,
            'slides': category.prefetched_slides,
        }
        for category in categories
    ]
    total_slides = active_slides().count()
    return render(request, 'index.html', {
        'category_sections': category_sections,
        'uncategorized_slides': uncategorized_slides,
        'total_slides': total_slides,
        'total_categories': len(categories),
        'sort': sort,
        'sort_options': SORT_OPTIONS,
        'database_options': database_options(),
        'current_database': display_db_name(current_db_path()),
        'trash_count': Slide.objects.filter(deleted_at__isnull=False).count(),
    })


@login_required
@require_POST
def switch_database(request):
    selected = request.POST.get('database', '').strip()
    allowed = {str(path): path for path in discover_db_paths()}
    target = allowed.get(selected)
    if not target:
        messages.error(request, '未找到这个数据库。')
        return redirect('index')

    compatible, reason = db_compatibility(target)
    if not compatible:
        messages.error(request, f'{display_db_name(target)} 不能用于管理主页：{reason}。')
        return redirect('index')

    apply_database(target)
    messages.success(request, f'已切换到 {display_db_name(target)}。')
    return redirect('index')

@login_required
def create_slide(request):
    # 获取当前文件所在的目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 默认内容文件的路径
    default_content_path = os.path.join(current_dir, 'default_content.md')

    # 读取默认内容
    with open(default_content_path, 'r', encoding='utf-8') as f:
        default_content = f.read()

    # 创建新的幻灯片，并设置默认内容
    next_order = (active_slides().filter(category_ref__isnull=True).aggregate(Max('sort_order'))['sort_order__max'] or 0) + 1
    slide = Slide.objects.create(
        title='未命名',
        content=default_content,
        lock=True,
        sort_order=next_order,
    )

    return redirect('edit_slide', slide_id=slide.id)

@login_required
def edit_slide(request, slide_id):
    slide = get_object_or_404(active_slides(), id=slide_id)
    return render(request, 'edit_slide.html', {'slide': slide})

@login_required
@require_POST
def delete_slide(request, slide_id):
    slide = get_object_or_404(active_slides(), id=slide_id)
    slide.deleted_at = timezone.now()
    slide.save(update_fields=['deleted_at'])
    return JsonResponse({'status': 'success'})


@login_required
def trash(request):
    slides = Slide.objects.filter(deleted_at__isnull=False).order_by('-deleted_at')
    return render(request, 'trash.html', {'slides': slides})


@login_required
@require_POST
def restore_slide(request, slide_id):
    slide = get_object_or_404(Slide, id=slide_id, deleted_at__isnull=False)
    slide.deleted_at = None
    # 原分类可能已被删除（SET_NULL 已处理外键），冗余的 category 文本一并清掉
    if slide.category_ref is None:
        slide.category = ''
        slide.save(update_fields=['deleted_at', 'category'])
    else:
        slide.save(update_fields=['deleted_at'])
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def purge_slide(request, slide_id):
    slide = get_object_or_404(Slide, id=slide_id, deleted_at__isnull=False)
    slide.delete()
    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def toggle_lock(request, slide_id):
    slide = get_object_or_404(active_slides(), id=slide_id)
    # 切换锁定状态
    slide.lock = not slide.lock
    slide.save()
    return JsonResponse({'status': 'success', 'lock': slide.lock})


@login_required
@require_POST
def update_category(request, slide_id):
    slide = get_object_or_404(active_slides(), id=slide_id)
    category = request.POST.get('category', '').strip()
    slide.category = category[:100]
    slide.save(update_fields=['category', 'updated_at'])
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect('index')


@login_required
@require_POST
def create_category(request):
    name = request.POST.get('name', '').strip()[:100]
    if not name:
        return JsonResponse({'error': '分类名称不能为空'}, status=400)

    position = (SlideCategory.objects.aggregate(Max('position'))['position__max'] or 0) + 1
    category, created = SlideCategory.objects.get_or_create(
        name=name,
        defaults={'position': position},
    )
    return JsonResponse({
        'status': 'success',
        'created': created,
        'category': {'id': category.id, 'name': category.name},
    })


@login_required
@require_POST
def rename_category(request, category_id):
    category = get_object_or_404(SlideCategory, id=category_id)
    name = request.POST.get('name', '').strip()[:100]
    if not name:
        return JsonResponse({'error': '分类名称不能为空'}, status=400)
    if SlideCategory.objects.exclude(id=category.id).filter(name=name).exists():
        return JsonResponse({'error': '这个分类名已经存在'}, status=400)

    category.name = name
    category.save(update_fields=['name', 'updated_at'])
    Slide.objects.filter(category_ref=category).update(category=name)
    return JsonResponse({'status': 'success', 'name': category.name})


@login_required
@require_POST
def delete_category(request, category_id):
    category = get_object_or_404(SlideCategory, id=category_id)
    action = request.POST.get('action')

    if action not in ('uncategorize', 'delete_slides'):
        return JsonResponse({'error': '无效的删除方式'}, status=400)

    with transaction.atomic():
        category_slides = category.slides.filter(deleted_at__isnull=True)
        slide_count = category_slides.count()
        if action == 'uncategorize':
            next_order = (active_slides().filter(category_ref__isnull=True).aggregate(Max('sort_order'))['sort_order__max'] or 0) + 1
            to_update = []
            for offset, slide in enumerate(category_slides.order_by('sort_order', '-updated_at', '-id')):
                slide.category_ref = None
                slide.category = ''
                slide.sort_order = next_order + offset
                to_update.append(slide)
            if to_update:
                Slide.objects.bulk_update(to_update, ['category_ref', 'category', 'sort_order'])
        else:
            # 软删除进回收站（回收站里仍可恢复或彻底删除）
            category_slides.update(deleted_at=timezone.now())

        category.delete()

    return JsonResponse({'status': 'success', 'slide_count': slide_count})


@login_required
@require_POST
def reorder_slides(request):
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except json.JSONDecodeError:
        return JsonResponse({'error': '无效的排序数据'}, status=400)

    category_id = payload.get('category_id')
    slide_ids = payload.get('slide_ids')
    if not isinstance(slide_ids, list):
        return JsonResponse({'error': 'slide_ids 必须是数组'}, status=400)

    category = None
    if category_id not in (None, '', 'uncategorized'):
        category = get_object_or_404(SlideCategory, id=category_id)

    clean_ids = []
    for slide_id in slide_ids:
        try:
            clean_ids.append(int(slide_id))
        except (TypeError, ValueError):
            return JsonResponse({'error': 'slide id 无效'}, status=400)

    with transaction.atomic():
        slides = {slide.id: slide for slide in active_slides().filter(id__in=clean_ids)}
        to_update = []
        for position, slide_id in enumerate(clean_ids):
            slide = slides.get(slide_id)
            if not slide:
                continue
            slide.category_ref = category
            slide.category = category.name if category else ''
            slide.sort_order = position
            to_update.append(slide)
        if to_update:
            Slide.objects.bulk_update(to_update, ['category_ref', 'category', 'sort_order'])

    return JsonResponse({'status': 'success'})


def public_slides(request):
    sort = get_sort(request)
    slide_ordering = SORT_OPTIONS[sort]
    categories = list(get_slide_categories(slide_ordering, slide_filter={'lock': False}))
    categories = [c for c in categories if c.prefetched_slides]
    uncategorized_slides = list(
        active_slides().filter(lock=False, category_ref__isnull=True).order_by(*slide_ordering)
    )
    category_sections = [
        {
            'id': category.id,
            'name': category.name,
            'slides': category.prefetched_slides,
        }
        for category in categories
    ]
    total_slides = active_slides().filter(lock=False).count()
    return render(request, 'public_slides.html', {
        'category_sections': category_sections,
        'uncategorized_slides': uncategorized_slides,
        'total_slides': total_slides,
        'total_categories': len(categories),
        'sort': sort,
        'sort_options': SORT_OPTIONS,
    })

def public_edit_slide(request, slide_id):
    slide = get_object_or_404(active_slides(), id=slide_id, lock=False)

    try:
        slide_html = convert_and_cache(slide, slide.content)
    except Exception as e:
        error_message = ''.join(traceback.format_exception_only(type(e), e))
        slide_html = f"<p>转换失败: {error_message}</p>"

    return render(request, 'public_edit_slide.html', {'slide': slide, 'slide_html': slide_html})
