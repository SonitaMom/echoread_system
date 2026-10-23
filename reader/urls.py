from django.urls import path
from . import views

app_name = "reader"

urlpatterns = [
    path("", views.document_list, name="document_list"),
    path(
        "<int:pk>/",
        views.document_detail,
        name="document_detail",
    ),
    
]
