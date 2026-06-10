# slideapp/urls.py

from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.index, name='index'),
    path('database/switch/', views.switch_database, name='switch_database'),
    path('create/', views.create_slide, name='create_slide'),
    path('edit/<int:slide_id>/', views.edit_slide, name='edit_slide'),
    path('upload_image/', views.upload_image, name='upload_image'),
    path('delete/<int:slide_id>/', views.delete_slide, name='delete_slide'),
    path('trash/', views.trash, name='trash'),
    path('trash/<int:slide_id>/restore/', views.restore_slide, name='restore_slide'),
    path('trash/<int:slide_id>/purge/', views.purge_slide, name='purge_slide'),
    path('category/<int:slide_id>/', views.update_category, name='update_category'),
    path('categories/create/', views.create_category, name='create_category'),
    path('categories/<int:category_id>/rename/', views.rename_category, name='rename_category'),
    path('categories/<int:category_id>/delete/', views.delete_category, name='delete_category'),
    path('slides/reorder/', views.reorder_slides, name='reorder_slides'),
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('toggle_lock/<int:slide_id>/', views.toggle_lock, name='toggle_lock'),
    path('present/<int:slide_id>/', views.present_slide, name='present_slide'),
    path('public/', views.public_slides, name='public_slides'),
    path('public/edit/<int:slide_id>/', views.public_edit_slide, name='public_edit_slide'),

]
