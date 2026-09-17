/* Adres-autocomplete voor het klusformulier, op basis van OpenStreetMap /
   Nominatim: geen API-sleutel en geen account nodig, past bij een app voor
   zes medewerkers. Typen in het adresveld toont suggesties eronder; een klik
   vult adres én plaats. Werkt de suggestie niet (geen internet, niets
   gevonden), dan blijft het gewoon een tekstveld — niks breekt. */
(function () {
  const adresVeld = document.getElementById("id_adres");
  const plaatsVeld = document.getElementById("id_plaats");
  if (!adresVeld) return;

  adresVeld.setAttribute("autocomplete", "off");

  const lijst = document.createElement("ul");
  lijst.className = "adres-suggesties";
  lijst.hidden = true;
  document.body.appendChild(lijst);

  let wachttimer = null;
  let eigenVerzoek = 0;

  function verbergen() {
    lijst.hidden = true;
    lijst.innerHTML = "";
  }

  function plaatsLijst() {
    const rect = adresVeld.getBoundingClientRect();
    lijst.style.top = rect.bottom + "px";
    lijst.style.left = rect.left + "px";
    lijst.style.width = rect.width + "px";
  }

  function toon(resultaten) {
    lijst.innerHTML = "";
    if (!resultaten.length) {
      verbergen();
      return;
    }
    resultaten.forEach(function (plek) {
      const regel = document.createElement("li");
      regel.textContent = plek.label;
      // mousedown i.p.v. click: vuurt vóór het blur-event dat de lijst verbergt.
      regel.addEventListener("mousedown", function (gebeurtenis) {
        gebeurtenis.preventDefault();
        adresVeld.value = plek.adres;
        if (plaatsVeld && plek.plaats) plaatsVeld.value = plek.plaats;
        verbergen();
      });
      lijst.appendChild(regel);
    });
    plaatsLijst();
    lijst.hidden = false;
  }

  function zoek(tekst) {
    const ditVerzoek = ++eigenVerzoek;
    const url =
      "https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1" +
      "&countrycodes=nl&limit=5&q=" + encodeURIComponent(tekst);
    fetch(url, { headers: { "Accept-Language": "nl" } })
      .then(function (antwoord) {
        return antwoord.ok ? antwoord.json() : [];
      })
      .then(function (data) {
        if (ditVerzoek !== eigenVerzoek) return; // ondertussen alweer verdergetypt
        toon(
          data.map(function (plek) {
            const a = plek.address || {};
            const straat = [a.road, a.house_number].filter(Boolean).join(" ");
            const plaats = a.city || a.town || a.village || a.municipality || "";
            return {
              label: plek.display_name,
              adres: straat || plek.display_name.split(",")[0],
              plaats: plaats,
            };
          })
        );
      })
      .catch(verbergen);
  }

  adresVeld.addEventListener("input", function () {
    clearTimeout(wachttimer);
    const tekst = adresVeld.value.trim();
    if (tekst.length < 4) {
      verbergen();
      return;
    }
    wachttimer = setTimeout(function () {
      zoek(tekst);
    }, 400);
  });

  adresVeld.addEventListener("blur", function () {
    setTimeout(verbergen, 150);
  });

  window.addEventListener("scroll", verbergen, true);
  window.addEventListener("resize", verbergen);
})();
