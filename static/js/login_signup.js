document.querySelectorAll("[data-show]").forEach(function (link){
    link.addEventListener("click", function (e) {
        e.preventDefault();
        var target= link.getAttribute("data-show");
        document.getElementById("login-view").hidden = target !== "login-view";
        document.getElementById("register-view").hidden = target !== "register-view";
    });
});