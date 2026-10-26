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

    # path("new-reader/", views.new_reader, name="new_reader"),
    # path("edit-reader/<str:pdf_name>/", views.edit_reader, name="edit_reader"),
    # path("<str:pdf_name>/", views.reader, name="reader"),

    path(
        "<int:pk>/edit/",
        views.edit_reader,
        name="edit_reader",
    ),
    path(
        "<int:pk>/save/",
        views.save_reader,
        name="save_reader",
    ),


    path("new/", views.new_reader, name="new_reader"),




]





