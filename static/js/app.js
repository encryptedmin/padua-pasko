const page = document.body.dataset.page;
const pageModules = {
  enter: () => import("./pages/enter.js"),
  "pick-name": () => import("./pages/pick-name.js"),
  bowl: () => import("./pages/bowl.js"),
  "my-pick": () => import("./pages/my-pick.js"),
  wishlists: () => import("./pages/wishlists.js"),
  manage: () => import("./pages/manage.js"),
  "manage-login": () => import("./pages/manage.js"),
};

if (pageModules[page]) {
  pageModules[page]().then((module) => module.init()).catch(() => {
    const region = document.querySelector("[role=alert]");
    if (region) region.textContent = "Page controls could not be loaded. Please refresh and try again.";
  });
}
