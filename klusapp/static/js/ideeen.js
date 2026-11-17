/* Ideeënbus: liken zonder dat de pagina herlaadt (ideeen/views.py idee_like).
   Zonder dit script werkt de knop als gewoon formulier. */
(function () {
  document.querySelectorAll(".idee-like-form").forEach(function (formulier) {
    formulier.addEventListener("submit", function (gebeurtenis) {
      gebeurtenis.preventDefault();
      var knop = formulier.querySelector(".idee-like");
      var aantal = knop.querySelector(".idee-aantal");
      var was = knop.classList.contains("geliket");
      // Meteen laten zien, zoals in elke app; bij een fout terugzetten.
      knop.classList.toggle("geliket", !was);
      knop.setAttribute("aria-pressed", String(!was));
      aantal.textContent = (parseInt(aantal.textContent, 10) || 0) + (was ? -1 : 1);
      fetch(formulier.action, {
        method: "POST",
        body: new FormData(formulier),
        headers: { "X-Idee": "1" },
        credentials: "same-origin",
      })
        .then(function (antwoord) { if (!antwoord.ok) throw new Error(); return antwoord.json(); })
        .then(function (data) {
          knop.classList.toggle("geliket", data.geliket);
          knop.setAttribute("aria-pressed", String(data.geliket));
          aantal.textContent = data.aantal;
          knop.setAttribute("aria-label", "Like, nu " + data.aantal);
        })
        .catch(function () {
          knop.classList.toggle("geliket", was);
          knop.setAttribute("aria-pressed", String(was));
          aantal.textContent = (parseInt(aantal.textContent, 10) || 0) + (was ? 1 : -1);
        });
    });
  });
})();
