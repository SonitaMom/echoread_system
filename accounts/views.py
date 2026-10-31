from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import RegisterForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages

import re
from django import template

def home_view(request):
    return render(request, "accounts/home.html")

def register_view(request):
    if request.user.is_authenticated:
        return redirect("reader:document_list")

    if request.method == "POST":
        form = RegisterForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})





def login_view(request):
    if request.user.is_authenticated:
        return redirect("reader:document_list")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("reader:document_list")

        messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


register = template.Library()

@register.filter
def initials(username):
    parts = [p for p in re.split(r'[._\-\s]+', username) if p]
    if len(parts)>=2:
        return (parts[0][0] + parts[1][0]).upper()
    return username[:2].upper()
