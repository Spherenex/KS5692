(function () {
  const key = "ks5692-dashboard-build";
  async function checkBuild() {
    try {
      const response = await fetch("/_ks5692-version", { cache: "no-store" });
      const data = await response.json();
      const previous = sessionStorage.getItem(key);
      if (previous && previous !== data.build) {
        sessionStorage.setItem(key, data.build);
        window.location.reload();
        return;
      }
      sessionStorage.setItem(key, data.build);
    } catch (_) {
      // A short server restart is expected during development.
    }
  }
  checkBuild();
  window.setInterval(checkBuild, 3000);
})();
