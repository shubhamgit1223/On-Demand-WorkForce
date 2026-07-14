function loadDashboard(){
    let user = localStorage.getItem("logged_user");
    if(!user){
        window.location.href = "login.html";
    }
    document.getElementById("welcome").innerText = "Welcome, " + user;
}