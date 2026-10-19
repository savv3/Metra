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

// New message form: show the tag or unit type choice only for its scope.
document.querySelectorAll("select[name=scope]").forEach((select) => {
  const show = () => {
    select.form.querySelectorAll("[data-scope-only]").forEach((part) => {
      part.hidden = part.dataset.scopeOnly !== select.value;
    });
  };
  select.addEventListener("change", show);
  show();
});

// Message form: show the SMS text and the email fields only for the channels
// that use them.
document.querySelectorAll("form").forEach((form) => {
  const radios = form.querySelectorAll("input[type=radio][name=channels]");
  if (!radios.length) return;
  const show = () => {
    const chosen = form.querySelector("input[name=channels]:checked");
    if (!chosen) return;
    form.querySelectorAll("[data-channels]").forEach((part) => {
      part.hidden = !part.dataset.channels.split(" ").includes(chosen.value);
    });
  };
  radios.forEach((radio) => radio.addEventListener("change", show));
  show();
});
