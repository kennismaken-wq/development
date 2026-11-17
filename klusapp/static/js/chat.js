/* De chat van een klus, als WhatsApp (templates/klussen/chat.html,
   klussen/chat.py).

   - Versturen zonder herladen. Elk bericht krijgt een eigen sleutel; komt
     het niet aan (slecht bereik), dan blijft het staan met "Niet verstuurd ·
     tik om opnieuw", en opnieuw versturen gebruikt dezelfde sleutel, zodat
     het nooit dubbel aankomt.
   - Elke paar seconden de nieuwe berichten ophalen, zolang de chat in beeld
     is; een weggehaald bericht verdwijnt dan ook bij de anderen.
   - De typbalk groeit mee met wat je typt; op een computer verstuurt Enter,
     Shift+Enter is een nieuwe regel. Op een telefoon is Enter een nieuwe
     regel en verstuur je met de knop, zoals in WhatsApp.
   - Gekozen foto's staan als voorbeeldje boven de typbalk.

   Zonder dit script is het een gewoon formulier dat de pagina herlaadt. */
(function () {
  var lijst = document.getElementById("chat-lijst");
  var vak = document.getElementById("chat-berichten");
  var formulier = document.getElementById("chat-invoer");
  if (!lijst || !vak || !formulier) return;

  var tekstveld = document.getElementById("chat-tekst");
  var fotoveld = document.getElementById("chat-fotos");
  var voorbeeld = document.getElementById("chat-voorbeeld");
  var naarOnder = document.getElementById("chat-naar-onder");
  var nieuwAantal = document.getElementById("chat-nieuw-aantal");
  var csrf = formulier.querySelector("[name=csrfmiddlewaretoken]").value;
  var nieuwUrl = vak.dataset.nieuwUrl;
  var laatste = parseInt(vak.dataset.laatste, 10) || 0;
  var maxFotos = parseInt(formulier.dataset.maxFotos, 10) || 10;
  var telefoon = window.matchMedia("(pointer: coarse)").matches;
  var POLL = 4000;
  var gemist = 0;

  // Zelfde meldingen onderin beeld als in de rest van de app (meldingen.js).
  function toonMelding(tekst) {
    var lijstje = document.querySelector(".meldingen");
    if (!lijstje) {
      lijstje = document.createElement("ul");
      lijstje.className = "meldingen";
      lijstje.setAttribute("role", "status");
      lijstje.setAttribute("aria-live", "polite");
      document.body.appendChild(lijstje);
    }
    var regel = document.createElement("li");
    regel.className = "melding error";
    regel.textContent = tekst;
    lijstje.appendChild(regel);
    setTimeout(function () { regel.remove(); }, 6000);
  }

  function sleutel() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "s" + Date.now().toString(36) + Math.random().toString(36).slice(2, 12);
  }

  function onderaan() {
    return vak.scrollHeight - vak.scrollTop - vak.clientHeight < 120;
  }

  function scrollNaarOnder(zacht) {
    vak.scrollTo({ top: vak.scrollHeight, behavior: zacht ? "smooth" : "auto" });
    gemist = 0;
    naarOnder.hidden = true;
  }

  // Bij het openen meteen onderaan, en nog eens als de foto's geladen zijn
  // (die maken de berichten hoger).
  scrollNaarOnder(false);
  lijst.querySelectorAll("img").forEach(function (img) {
    if (!img.complete) img.addEventListener("load", function () { if (onderaan() || !gemist) scrollNaarOnder(false); }, { once: true });
  });
  // Lazy: dan laadt een foto pas als hij in beeld komt; hier willen we de
  // onderste meteen.
  lijst.querySelectorAll("img[loading=lazy]").forEach(function (img) { img.loading = "eager"; });

  vak.addEventListener("scroll", function () {
    if (onderaan()) { gemist = 0; naarOnder.hidden = true; }
  });
  naarOnder.addEventListener("click", function () { scrollNaarOnder(true); });

  /* ---- Berichten in de lijst zetten ---- */

  function maakElementen(html) {
    var houder = document.createElement("div");
    houder.innerHTML = html;
    return Array.prototype.slice.call(houder.children);
  }

  function laatsteDag() {
    var dagen = lijst.querySelectorAll(".chat-dag");
    return dagen.length ? dagen[dagen.length - 1].dataset.dag : null;
  }

  function voegToe(html, voor) {
    var leeg = document.getElementById("chat-leeg");
    if (leeg) leeg.remove();
    maakElementen(html).forEach(function (el) {
      if (el.classList.contains("chat-dag") && el.dataset.dag === laatsteDag() && !voor) return;
      if (el.dataset.pk && document.getElementById("bericht-" + el.dataset.pk)) return;
      if (voor) lijst.insertBefore(el, voor);
      else lijst.appendChild(el);
      el.querySelectorAll("form.chat-weg").forEach(koppelWeg);
      el.querySelectorAll("img").forEach(function (img) {
        img.addEventListener("load", function () { if (onderaan()) scrollNaarOnder(false); }, { once: true });
      });
    });
  }

  // Een datumkop zonder berichten eronder (alles van die dag weggehaald) weg.
  function ruimDagenOp() {
    lijst.querySelectorAll(".chat-dag").forEach(function (dag) {
      var volgende = dag.nextElementSibling;
      if (!volgende || volgende.classList.contains("chat-dag")) dag.remove();
    });
  }

  /* ---- Versturen ---- */

  function wachtend(tekst, fotos) {
    var el = document.createElement("div");
    el.className = "chat-bericht eigen bezig";
    var ballon = document.createElement("div");
    ballon.className = "ballon";
    if (fotos.length) {
      var raster = document.createElement("div");
      raster.className = "chat-fotos aantal-" + Math.min(fotos.length, 4);
      fotos.slice(0, 4).forEach(function (bestand) {
        var knop = document.createElement("span");
        var img = document.createElement("img");
        img.src = URL.createObjectURL(bestand);
        img.alt = "";
        knop.appendChild(img);
        raster.appendChild(knop);
      });
      ballon.appendChild(raster);
    }
    if (tekst) {
      var p = document.createElement("p");
      p.className = "chat-tekst";
      p.textContent = tekst;
      ballon.appendChild(p);
    }
    var tijd = document.createElement("span");
    tijd.className = "chat-tijd";
    tijd.textContent = "Versturen…";
    ballon.appendChild(tijd);
    el.appendChild(ballon);
    var leeg = document.getElementById("chat-leeg");
    if (leeg) leeg.remove();
    lijst.appendChild(el);
    scrollNaarOnder(false);
    return el;
  }

  function verstuur(gegevens, el) {
    el.classList.add("bezig");
    el.classList.remove("mislukt");
    el.querySelector(".chat-tijd").textContent = "Versturen…";
    fetch(formulier.action, {
      method: "POST",
      body: gegevens,
      headers: { "X-Chat": "1", "X-CSRFToken": csrf },
      credentials: "same-origin",
    })
      .then(function (antwoord) {
        return antwoord.json().then(function (data) { return { ok: antwoord.ok, status: antwoord.status, data: data }; },
          function () { return { ok: false, status: antwoord.status, data: {} }; });
      })
      .then(function (uitkomst) {
        if (uitkomst.ok && uitkomst.data.html) {
          var bestaand = document.getElementById("bericht-" + uitkomst.data.pk);
          if (bestaand) { el.remove(); }
          else {
            maakElementen(uitkomst.data.html).forEach(function (nieuw) {
              if (nieuw.classList.contains("chat-dag")) {
                if (nieuw.dataset.dag !== laatsteDag()) lijst.insertBefore(nieuw, el);
                return;
              }
              el.replaceWith(nieuw);
              nieuw.querySelectorAll("form.chat-weg").forEach(koppelWeg);
            });
          }
          laatste = Math.max(laatste, uitkomst.data.pk);
          (uitkomst.data.meldingen || []).forEach(toonMelding);
          scrollNaarOnder(false);
        } else if (uitkomst.status >= 400 && uitkomst.status < 500 && uitkomst.data.fout) {
          // De server wil dit bericht niet (te lang, verkeerd bestand): niet
          // opnieuw proberen, wel zeggen waarom.
          el.classList.remove("bezig");
          el.classList.add("geweigerd");
          el.querySelector(".chat-tijd").textContent = uitkomst.data.fout;
        } else {
          mislukt(gegevens, el);
        }
      })
      .catch(function () { mislukt(gegevens, el); });
  }

  function mislukt(gegevens, el) {
    el.classList.remove("bezig");
    el.classList.add("mislukt");
    var tijd = el.querySelector(".chat-tijd");
    tijd.textContent = "Niet verstuurd · tik om opnieuw";
    el.onclick = function () {
      el.onclick = null;
      verstuur(gegevens, el);
    };
  }

  formulier.addEventListener("submit", function (gebeurtenis) {
    gebeurtenis.preventDefault();
    var tekst = tekstveld.value.trim();
    var fotos = Array.prototype.slice.call(fotoveld.files || []);
    if (!tekst && !fotos.length) { tekstveld.focus(); return; }
    var gegevens = new FormData(formulier);
    gegevens.set("tekst", tekst);
    gegevens.set("sleutel", sleutel());
    var el = wachtend(tekst, fotos);
    tekstveld.value = "";
    fotoveld.value = "";
    toonVoorbeeld();
    pasHoogteAan();
    verstuur(gegevens, el);
    if (!telefoon) tekstveld.focus();
  });

  tekstveld.addEventListener("keydown", function (gebeurtenis) {
    if (gebeurtenis.key === "Enter" && !gebeurtenis.shiftKey && !telefoon && !gebeurtenis.isComposing) {
      gebeurtenis.preventDefault();
      formulier.requestSubmit();
    }
  });

  /* ---- Typbalk groeit mee, tot ongeveer vijf regels ---- */

  function pasHoogteAan() {
    tekstveld.style.height = "auto";
    tekstveld.style.height = Math.min(tekstveld.scrollHeight, 132) + "px";
  }
  tekstveld.addEventListener("input", pasHoogteAan);

  /* ---- Gekozen foto's als voorbeeldje ---- */

  function toonVoorbeeld() {
    var bestanden = Array.prototype.slice.call(fotoveld.files || []);
    voorbeeld.innerHTML = "";
    voorbeeld.hidden = !bestanden.length;
    if (!bestanden.length) return;
    bestanden.slice(0, maxFotos).forEach(function (bestand) {
      var img = document.createElement("img");
      img.src = URL.createObjectURL(bestand);
      img.alt = "";
      voorbeeld.appendChild(img);
    });
    var tekst = document.createElement("span");
    tekst.className = "chat-voorbeeld-tekst";
    tekst.textContent = bestanden.length > maxFotos
      ? "Alleen de eerste " + maxFotos + " foto's gaan mee"
      : bestanden.length + (bestanden.length === 1 ? " foto" : " foto's");
    voorbeeld.appendChild(tekst);
    var weg = document.createElement("button");
    weg.type = "button";
    weg.className = "chat-voorbeeld-weg";
    weg.setAttribute("aria-label", "Foto's weghalen");
    weg.textContent = "×";
    weg.onclick = function () { fotoveld.value = ""; toonVoorbeeld(); };
    voorbeeld.appendChild(weg);
  }
  fotoveld.addEventListener("change", function () {
    toonVoorbeeld();
    if (!telefoon) tekstveld.focus();
  });

  /* ---- Weghalen: tik op je eigen bericht, dan "Verwijderen" ---- */

  function koppelWeg(form) {
    form.addEventListener("submit", function (gebeurtenis) {
      gebeurtenis.preventDefault();
      if (!window.confirm("Dit bericht verwijderen?")) return;
      var bericht = form.closest(".chat-bericht");
      fetch(form.action, {
        method: "POST",
        headers: { "X-Chat": "1", "X-CSRFToken": csrf },
        credentials: "same-origin",
      }).then(function (antwoord) {
        if (antwoord.ok) { bericht.remove(); ruimDagenOp(); }
        else toonMelding("Verwijderen lukte niet. Probeer het zo nog eens.");
      }, function () { toonMelding("Geen verbinding. Probeer het zo nog eens."); });
    });
    form.removeAttribute("onsubmit");
  }
  lijst.querySelectorAll("form.chat-weg").forEach(koppelWeg);

  lijst.addEventListener("click", function (gebeurtenis) {
    if (gebeurtenis.target.closest("button, a, form")) return;
    var bericht = gebeurtenis.target.closest(".chat-bericht");
    lijst.querySelectorAll(".chat-bericht.gekozen").forEach(function (ander) {
      if (ander !== bericht) ander.classList.remove("gekozen");
    });
    if (bericht && bericht.querySelector("form.chat-weg")) bericht.classList.toggle("gekozen");
  });

  /* ---- Nieuwe berichten ophalen ---- */

  var bezigMetOphalen = false;
  function haalNieuwe() {
    if (bezigMetOphalen || document.hidden) return;
    bezigMetOphalen = true;
    // Het laagste nummer op het scherm: alles vanaf daar hoort er nog te zijn.
    var nummers = Array.prototype.map.call(lijst.querySelectorAll(".chat-bericht[data-pk]"), function (el) { return parseInt(el.dataset.pk, 10); });
    var eerste = nummers.length ? Math.min.apply(null, nummers) : 0;
    var url = nieuwUrl + "?na=" + laatste + "&zichtbaar=1" + (eerste ? "&van=" + eerste : "");
    fetch(url, { credentials: "same-origin", headers: { "X-Chat": "1" } })
      .then(function (antwoord) { return antwoord.ok ? antwoord.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (data.nog_er && data.nog_er.length && eerste) {
          var er = {};
          data.nog_er.forEach(function (pk) { er[pk] = true; });
          lijst.querySelectorAll(".chat-bericht[data-pk]").forEach(function (el) {
            if (!er[el.dataset.pk]) el.remove();
          });
          ruimDagenOp();
        }
        if (data.html) {
          var wasOnder = onderaan();
          var voor = lijst.querySelectorAll(".chat-bericht[data-pk]").length;
          voegToe(data.html);
          var erbij = lijst.querySelectorAll(".chat-bericht[data-pk]").length - voor;
          if (wasOnder) scrollNaarOnder(true);
          else if (erbij > 0) {
            gemist += erbij;
            nieuwAantal.textContent = gemist;
            naarOnder.hidden = false;
          }
        }
        laatste = Math.max(laatste, data.laatste || 0);
      })
      .catch(function () {})
      .then(function () { bezigMetOphalen = false; });
  }
  setInterval(haalNieuwe, POLL);
  document.addEventListener("visibilitychange", function () { if (!document.hidden) haalNieuwe(); });
  window.addEventListener("online", haalNieuwe);
})();
