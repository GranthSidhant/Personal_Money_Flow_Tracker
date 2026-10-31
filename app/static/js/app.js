/**
 * Personal Money Flow Tracker - Core Client-Side Utilities
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Theme Toggle System
    const themeToggleBtn = document.getElementById("theme-toggle-btn");
    const themeIcon = document.getElementById("theme-icon");
    
    // Check saved theme or system preference
    const savedTheme = localStorage.getItem("theme") || 
        (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    
    function applyTheme(theme) {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
        if (themeIcon) {
            themeIcon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
        }
    }
    
    applyTheme(savedTheme);
    
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener("click", () => {
            const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
            const newTheme = currentTheme === "dark" ? "light" : "dark";
            applyTheme(newTheme);
        });
    }

    // 2. Mobile Sidebar Toggle
    const sidebarToggleBtn = document.getElementById("sidebar-toggle-btn");
    const sidebar = document.querySelector(".app-sidebar");
    
    if (sidebarToggleBtn && sidebar) {
        sidebarToggleBtn.addEventListener("click", () => {
            sidebar.classList.toggle("show");
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener("click", (e) => {
            if (sidebar.classList.contains("show") && 
                !sidebar.contains(e.target) && 
                !sidebarToggleBtn.contains(e.target)) {
                sidebar.classList.remove("show");
            }
        });
    }

    // 3. Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll(".alert-dismissible");
    alerts.forEach((alert) => {
        setTimeout(() => {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) bsAlert.close();
        }, 5000);
    });
});
