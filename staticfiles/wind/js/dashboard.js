(function () {
  if (!WindAuth.isLoggedIn()) {
    window.location.href = "/wind/login/";
    return;
  }

  const els = {
    greeting: document.getElementById("user-greeting"),
    name: document.getElementById("user-name"),
    email: document.getElementById("user-email"),
    code: document.getElementById("user-code"),
    products: document.getElementById("products-list"),
    passwordAlert: document.getElementById("password-alert"),
  };

  let profile = null;

  function showModuleAlert(message, type) {
    els.passwordAlert.textContent = message;
    els.passwordAlert.className = "app-alert show " + (type || "error");
  }

  async function loadProfile() {
    const res = await WindAuth.fetchApi("/api/v1/profile/me/");
    const data = await res.json();
    if (!res.ok || !data.success) {
      throw new Error(data.message || "No se pudo cargar el perfil");
    }
    profile = data.profile;
    const name = [profile.first_name, profile.last_name].filter(Boolean).join(" ") || profile.email;
    els.greeting.textContent = "Hola, " + (profile.first_name || profile.email);
    els.name.textContent = name;
    els.email.textContent = profile.email || "—";
    els.code.textContent = profile.subscriber_code || "Sin vincular";
  }

  async function loadProducts() {
    els.products.textContent = "Cargando productos…";
    try {
      const res = await WindAuth.fetchApi("/api/v1/profile/products/?page_size=8");
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.message || "Error al cargar productos");
      }
      if (!data.results || !data.results.length) {
        els.products.innerHTML = "<p>No hay productos en el catálogo local.</p>";
        return;
      }
      const list = document.createElement("ul");
      list.style.margin = "0";
      list.style.paddingLeft = "18px";
      data.results.forEach((p) => {
        const li = document.createElement("li");
        li.textContent = (p.name || "Producto") + " (ID " + p.productId + ")";
        list.appendChild(li);
      });
      els.products.innerHTML = "";
      els.products.appendChild(list);
      if (data.total_pages > 1) {
        const more = document.createElement("p");
        more.style.marginTop = "8px";
        more.textContent = "Mostrando página " + data.page + " de " + data.total_pages;
        els.products.appendChild(more);
      }
    } catch (err) {
      els.products.textContent = err.message;
    }
  }

  document.getElementById("password-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!profile || !profile.subscriber_code) {
      showModuleAlert("Tu usuario no tiene un suscriptor vinculado.", "error");
      return;
    }
    const newPass = document.getElementById("newPass").value;
    try {
      const res = await WindAuth.fetchApi("/api/v1/profile/password/", {
        method: "POST",
        body: JSON.stringify({ code: profile.subscriber_code, newPass: newPass }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.message || "No se pudo cambiar la contraseña");
      }
      showModuleAlert("Contraseña actualizada correctamente.", "success");
      document.getElementById("newPass").value = "";
    } catch (err) {
      showModuleAlert(err.message, "error");
    }
  });

  document.getElementById("btn-reload-products").addEventListener("click", loadProducts);

  document.getElementById("btn-logout").addEventListener("click", () => {
    WindAuth.logout();
    window.location.href = "/wind/login/";
  });

  (async function init() {
    try {
      await loadProfile();
      await loadProducts();
    } catch (err) {
      els.greeting.textContent = err.message;
    }
  })();
})();
