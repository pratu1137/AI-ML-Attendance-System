(() => {
    const toggle = document.querySelector("[data-menu-toggle]");
    const sidebar = document.querySelector("[data-sidebar]");
    if (!toggle || !sidebar) return;
    toggle.addEventListener("click", () => {
        const open = sidebar.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", String(open));
    });
})();