from django.urls import path
from . import views
from django.contrib.auth import views as auth_views


app_name = "reader"

# urlpatterns = [
#     path("", views.document_list, name="document_list"),

#     path(
#         "<int:pk>/tts/",
#         views.text_to_speech,
#         name="text_to_speech",
#     ),

#     path(
#         "<int:pk>/ai-helper/",
#         views.ai_helper_ajax,
#         name="ai_helper_ajax",
#     ),

#     path(
#         "<int:pk>/delete/",
#         views.delete_reader,
#         name="delete_reader",
#     ),

#     path(
#         "<int:pk>/",
#         views.document_detail,
#         name="document_detail",
#     ),

#     path(
#         "<int:pk>/bookmarks/create/",
#         views.create_bookmark,
#         name="create_bookmark",
#     ),
    
#     path(
#         "<int:pk>/bookmarks/<int:bookmark_id>/delete/",
#         views.delete_bookmark,
#         name="delete_bookmark",
#     ),

#     path(
#         "<int:pk>/edit/",
#         views.edit_reader,
#         name="edit_reader",
#     ),
#     path(
#         "<int:pk>/save/",
#         views.save_reader,
#         name="save_reader",
#     ),


#     path("new/", views.new_reader, name="new_reader"),


#     path(
#         "<int:pk>/notes/new/",
#         views.create_note,
#         name="create_note",
#     ),
#     path(
#         "<int:pk>/notes/<int:note_id>/edit/",
#         views.edit_note,
#         name="edit_note",
#     ),


#     path(
#         "<int:pk>/notes/save/",
#         views.save_note_ajax,
#         name="save_note_ajax",
#     ),

#     path(
#         "<int:pk>/notes/<int:note_id>/delete/",
#         views.delete_note_ajax,
#         name="delete_note_ajax",
#     ),



#     path(
#         "<int:pk>/ai/ask/",
#         views.ask_ai_ajax,
#         name="ask_ai_ajax",
#     ),




# ]


urlpatterns = [



    # Document list and creation
    path("", views.document_list, name="document_list"),
    path("new/", views.new_reader, name="new_reader"),

    # Document actions
    path("<int:pk>/", views.document_detail, name="document_detail"),
    path("<int:pk>/edit/", views.edit_reader, name="edit_reader"),
    path("<int:pk>/save/", views.save_reader, name="save_reader"),
    path("<int:pk>/delete/", views.delete_reader, name="delete_reader"),

    # Text-to-speech and AI
    path("<int:pk>/tts/", views.text_to_speech, name="text_to_speech"),
    path("<int:pk>/ai-helper/", views.ai_helper_ajax, name="ai_helper_ajax"),
    path("<int:pk>/ai/ask/", views.ask_ai_ajax, name="ask_ai_ajax"),

    # Bookmarks
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

    # Notes
    path("<int:pk>/notes/new/", views.create_note, name="create_note"),
    path(
        "<int:pk>/notes/<int:note_id>/edit/",
        views.edit_note,
        name="edit_note",
    ),
    path("<int:pk>/notes/save/", views.save_note_ajax, name="save_note_ajax"),
    path(
        "<int:pk>/notes/<int:note_id>/delete/",
        views.delete_note_ajax,
        name="delete_note_ajax",
    ),
]


