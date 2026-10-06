let cursor = document.getElementById("myCursor");
window.addEventListener("mousemove",function(e){
  let x = e.clientX;
  let y = e.clientY;
  cursor.style.left = x-25+"px";
  cursor.style.top = y-25+"px";
})