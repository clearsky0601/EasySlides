# slideapp/consumers.py

import json
import logging
import traceback

from asgiref.sync import sync_to_async
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .models import Slide
from .html_converter import convert_markdown, convert_and_cache

logger = logging.getLogger(__name__)


class SlideConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # 检查用户是否已登录
        if self.scope["user"] == AnonymousUser():
            await self.close()
        else:
            self.slide_id = self.scope['url_route']['kwargs'].get('slide_id')
            await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("收到无法解析的 WebSocket 消息，已忽略")
            return
        action = data.get('action')

        if action == 'load':
            slide_data = await self.get_slide_content()
            await self.send(text_data=json.dumps({
                'action': 'load',
                'content': slide_data['content'],
                'version': slide_data['version']
            }))
        elif action == 'save':
            markdown_content = data['markdown']
            client_version = data.get('version', -1)
            result = await self.save_slide_content(markdown_content, client_version)

            if result['conflict']:
                await self.send(text_data=json.dumps({
                    'action': 'reload',
                    'content': result['content'],
                    'version': result['version'],
                    'reason': 'conflict'
                }))
            else:
                html_result = await self._convert(markdown_content, use_model_cache=True)
                if isinstance(html_result, dict) and 'error' in html_result:
                    await self.send(text_data=json.dumps({
                        'action': 'error',
                        'message': html_result['error']
                    }))
                else:
                    await self.send(text_data=json.dumps({
                        'action': 'save_ok',
                        'version': result['version'],
                        'html': html_result
                    }))
        elif action == 'preview':
            markdown_content = data['markdown']
            result = await self._convert(markdown_content)
            if isinstance(result, dict) and 'error' in result:
                await self.send(text_data=json.dumps({
                    'action': 'error',
                    'message': result['error']
                }))
            else:
                await self.send(text_data=json.dumps({
                    'action': 'preview',
                    'html': result
                }))
        elif action == 'check_version':
            version = await self.get_slide_version()
            await self.send(text_data=json.dumps({
                'action': 'version_info',
                'version': version
            }))

    @sync_to_async
    def get_slide_content(self):
        slide = Slide.objects.get(id=self.slide_id)
        return {'content': slide.content, 'version': slide.version}

    @database_sync_to_async
    def get_slide_version(self):
        return Slide.objects.filter(id=self.slide_id).values_list('version', flat=True).first()

    @sync_to_async
    def save_slide_content(self, content, client_version):
        slide = Slide.objects.get(id=self.slide_id)
        if slide.version != client_version:
            return {'conflict': True, 'content': slide.content, 'version': slide.version}
        slide.content = content
        slide.version = slide.version + 1
        slide.title = slide.extract_title_from_content()
        slide.save()
        return {'conflict': False, 'version': slide.version}

    async def _convert(self, markdown_content, use_model_cache=False):
        try:
            if use_model_cache:
                slide = await sync_to_async(Slide.objects.get)(id=self.slide_id)
                return await sync_to_async(convert_and_cache)(slide, markdown_content)
            return await sync_to_async(convert_markdown)(markdown_content)
        except Exception as e:
            error_message = ''.join(traceback.format_exception_only(type(e), e))
            logger.warning("转换失败: %s", error_message)
            return {'error': error_message}


class PublicSlideConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.slide_id = self.scope['url_route']['kwargs'].get('slide_id')
        try:
            slide = await sync_to_async(Slide.objects.get)(id=self.slide_id)
        except Slide.DoesNotExist:
            await self.close()
            return
        if slide.lock:
            await self.close()
        else:
            await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("收到无法解析的 WebSocket 消息，已忽略")
            return
        action = data.get('action')

        if action == 'load':
            content = await self.get_slide_content()
            await self.send(text_data=json.dumps({
                'action': 'load',
                'content': content
            }))
        elif action == 'preview':
            markdown_content = data['markdown']
            try:
                html = await sync_to_async(convert_markdown)(markdown_content)
                await self.send(text_data=json.dumps({
                    'action': 'preview',
                    'html': html
                }))
            except Exception as e:
                error_message = ''.join(traceback.format_exception_only(type(e), e))
                logger.warning("转换失败: %s", error_message)
                await self.send(text_data=json.dumps({
                    'action': 'error',
                    'message': error_message
                }))

    @sync_to_async
    def get_slide_content(self):
        slide = Slide.objects.get(id=self.slide_id)
        return slide.content