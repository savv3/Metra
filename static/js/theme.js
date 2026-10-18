// Apply the light or dark theme picked in the account menu before the page
// draws, so it does not flash. Without a choice the device setting decides.
(function () {
  try {
    var theme = localStorage.getItem("theme");
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  } catch (e) {
    // Storage blocked: follow the device setting.
  }
})();
