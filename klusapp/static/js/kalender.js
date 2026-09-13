/* Slepen in de weekkalender.

   Met een muis sleep je over de halfuurvakken en laat je los; met een vinger
   is slepen niet te onderscheiden van scrollen, dus daar is een tik op één
   vak genoeg — de eindtijd vul je dan in het formulier in. */
(function () {
  const script = document.currentScript;
  const nieuwUrl = script.dataset.nieuwUrl;

  const START_MIN = 6 * 60;
  const VAK_MIN = 30;

  function tijd(vaknummer) {
    const minuut = START_MIN + vaknummer * VAK_MIN;
    return String(Math.floor(minuut / 60)).padStart(2, "0") + ":" +
           String(minuut % 60).padStart(2, "0");
  }

  function openFormulier(dag, vanVak, totVak) {
    // totVak is null bij een tik: dan alleen een begintijd meegeven.
    const van = totVak === null ? vanVak : Math.min(vanVak, totVak);
    let adres = nieuwUrl + "?dag=" + dag + "&van=" + tijd(van);
    if (totVak !== null) adres += "&tot=" + tijd(Math.max(vanVak, totVak) + 1);
    window.location.href = adres;
  }

  let muisGebruikt = false;

  document.querySelectorAll(".dagkolom").forEach(function (kolom) {
    let van = null, tot = null;

    function verf() {
      kolom.querySelectorAll(".vak").forEach(function (vak) {
        const index = Number(vak.dataset.vak);
        const binnen = van !== null && index >= Math.min(van, tot) && index <= Math.max(van, tot);
        vak.classList.toggle("kiezen", binnen);
      });
    }

    function wis() {
      van = tot = null;
      kolom.querySelectorAll(".vak").forEach(function (vak) {
        vak.classList.remove("kiezen");
      });
    }

    kolom.addEventListener("pointerdown", function (gebeurtenis) {
      if (gebeurtenis.pointerType !== "mouse") return;   // vingers scrollen
      muisGebruikt = true;
      const vak = gebeurtenis.target.closest(".vak");
      if (!vak) return;
      van = tot = Number(vak.dataset.vak);
      verf();
    });

    kolom.addEventListener("pointermove", function (gebeurtenis) {
      if (van === null) return;
      const vak = gebeurtenis.target.closest(".vak");
      if (!vak) return;
      tot = Number(vak.dataset.vak);
      verf();
    });

    kolom.addEventListener("pointerup", function () {
      if (van === null) return;
      const vanVak = van, totVak = tot;
      wis();
      openFormulier(kolom.dataset.dag, vanVak, totVak);
    });

    kolom.addEventListener("pointerleave", wis);

    // Op een aanraakscherm: een tik op een vak opent het formulier met dat
    // halfuur als begintijd.
    kolom.addEventListener("click", function (gebeurtenis) {
      if (muisGebruikt) return;   // de muis heeft het al via pointerup gedaan
      const vak = gebeurtenis.target.closest(".vak");
      if (!vak) return;
      openFormulier(kolom.dataset.dag, Number(vak.dataset.vak), null);
    });
  });
})();
