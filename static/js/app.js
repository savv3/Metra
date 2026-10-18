// Close the account menu when clicking elsewhere or pressing Escape.
document.addEventListener("click", (event) => {
  document.querySelectorAll(".user-menu[open]").forEach((menu) => {
    if (!menu.contains(event.target)) menu.open = false;
  });
});
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  document.querySelectorAll(".user-menu[open]").forEach((menu) => {
    menu.open = false;
    menu.querySelector("summary").focus();
  });
});

// Theme picker in the account menu: auto (device setting), light or dark.
document.querySelectorAll("[data-theme-select]").forEach((select) => {
  select.value = document.documentElement.dataset.theme || "auto";
  select.addEventListener("change", () => {
    const theme = select.value;
    if (theme === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    try {
      if (theme === "auto") localStorage.removeItem("theme");
      else localStorage.setItem("theme", theme);
    } catch (e) {
      // Storage blocked: the choice lasts until the page is left.
    }
  });
});
