from django.urls import path
from . import views

app_name = "reader"

urlpatterns = [
    path("", views.document_list, name="document_list"),

    path(
        "<int:pk>/tts/",
        views.text_to_speech,
        name="text_to_speech",
    ),

    path(
        "<int:pk>/",
        views.document_detail,
        name="document_detail",
    ),

    path(
        "<int:pk>/bookmarks/create/",
        views.create_bookmark,
        name="create_bookmark",
    ),
    
    path(
        "<int:pk>/bookmarks/<int:bookmark_id>/delete/",
        views.delete_bookmark,
        name="delete_bookmark",
    ),

]
