/**
 * ============================================================
 * SMART BUS - SIDEBAR & RESPONSIVE NAVIGATION CONTROLLER
 * ============================================================
 */

document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.querySelector('.admin-sidebar');
  const toggleBtn = document.querySelector('.mobile-toggle');
  
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('open');
    });
  }

  // Highlight active menu item based on current location
  const currentPath = window.location.pathname.split('/').pop() || 'dashboard.html';
  const menuLinks = document.querySelectorAll('.sidebar-menu .menu-item a');
  
  menuLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (href && (href === currentPath || (currentPath === '' && href === 'dashboard.html'))) {
      link.parentElement.classList.add('active');
    } else {
      link.parentElement.classList.remove('active');
    }
  });
});
