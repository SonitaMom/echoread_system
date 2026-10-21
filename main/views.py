from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")

def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(
            request,
            username=username,
            password=password
        )
        if user is not None:
            login(request, user)
            return redirect("dashboard")

        return render(request, "login.html", {
            "error": "Invalid username or password."
        })
    return render(request, "login.html")

def logout_view(request):
    logout(request)
    return redirect("login")




def pdf_view(request):
    # Logic to generate or serve a PDF file
    return render(request, "pdf_test.html")