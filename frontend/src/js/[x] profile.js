document.addEventListener('DOMContentLoaded', function() {
    const profileBtn = document.getElementById('profileBtn');
    const profileMenu = document.getElementById('profileMenu');
    
    profileBtn.addEventListener('click', function() {
        profileMenu.classList.toggle('show');
    });
    
    // 다른 곳을 클릭하면 메뉴 닫기
    document.addEventListener('click', function(event) {
        if (!profileBtn.contains(event.target) && !profileMenu.contains(event.target)) {
            profileMenu.classList.remove('show');
        }
    });
}); 