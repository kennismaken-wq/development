/* Bladeren op het jaarbord (Aanwezigheid en Mijn aanwezigheid).

   Het bord is altijd een heel jaar dat opzij scrolt; Dag, Week en Maand
   bepalen alleen hoe breed een dag is. Eerst sprongen de pijlen een heel jaar
   en hield de kop alleen het jaartal vast — in de weekzoom leek het alsof je
   per klik een jaar én een weekdag verschoof (Floris 03-10-2026). Nu:

   - de pijlen schuiven één periode van de gekozen zoom: een dag, een week
     (naar de maandag) of een maand (naar de 1e);
   - de kop zegt wat er links in beeld staat: "wo 1 okt 2026",
     "week 40 · 28 sep – 4 okt 2026" of "oktober 2026", en loopt mee met
     scrollen;
   - pas wie over de jaargrens bladert, laadt het andere jaar (gewone link).

   Verwacht in de pagina: [data-blader="-1"|"1"] op de pijlen,
   .periodetitel, het bord (#wp-bord of .wp-bord) met .wp-kop[data-k][data-iso]
   in de kopregel, en de klassen wp-zoom-dag/-week/-maand op het bord (die
   zetten werkplanning.js en mijn-aanwezigheid.js). */
(function () {
  const bord = document.querySelector(".wp-bord");
  const scroller = bord && bord.closest(".bord-scroll");
  const titel = document.querySelector(".navbalk .periodetitel");
  const pijlen = document.querySelectorAll("[data-blader]");
  if (!bord || !scroller || !pijlen.length) return;

  const koppen = Array.from(bord.querySelectorAll(".wp-kop[data-iso]"));
  const perDatum = {};
  koppen.forEach(function (kop) { perDatum[kop.dataset.iso] = kop; });

  function datum(iso) {
    const d = iso.split("-").map(Number);
    return new Date(d[0], d[1] - 1, d[2]);
  }
  function iso(d) {
    return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
  }
  function zoom() {
    if (bord.classList.contains("wp-zoom-dag")) return "dag";
    if (bord.classList.contains("wp-zoom-maand")) return "maand";
    return "week";
  }
  function namenBreedte() {
    const hoek = bord.querySelector(".bord-hoek");
    return hoek ? hoek.offsetWidth : 0;
  }

  // De eerste dag die (grotendeels) rechts van de namenkolom in beeld staat.
  function eersteInBeeld() {
    const links = scroller.getBoundingClientRect().left + namenBreedte();
    for (const kop of koppen) {
      const r = kop.getBoundingClientRect();
      if (r.left + r.width / 2 >= links) return datum(kop.dataset.iso);
    }
    return datum(koppen[koppen.length - 1].dataset.iso);
  }

  function naar(d, vloeiend) {
    const kop = perDatum[iso(d)];
    if (!kop) return false;
    const verschil = kop.getBoundingClientRect().left - scroller.getBoundingClientRect().left - namenBreedte();
    scroller.scrollTo({ left: scroller.scrollLeft + verschil, behavior: vloeiend ? "smooth" : "auto" });
    return true;
  }

  function maandag(d) {
    const m = new Date(d);
    m.setDate(m.getDate() - ((m.getDay() + 6) % 7));
    return m;
  }
  function weeknummer(d) {
    const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
    t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));
    const jaarbegin = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
    return Math.ceil(((t - jaarbegin) / 86400000 + 1) / 7);
  }
  const kort = { day: "numeric", month: "short" };

  function kopTekst(d) {
    d = d || eersteInBeeld();
    const z = zoom();
    if (z === "dag") {
      return d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
    }
    if (z === "maand") {
      return d.toLocaleDateString("nl-NL", { month: "long", year: "numeric" });
    }
    const ma = maandag(d);
    const zo = new Date(ma);
    zo.setDate(zo.getDate() + 6);
    // "5 – 11 okt 2026", "28 sep – 4 okt 2026", "28 dec 2026 – 3 jan 2027"
    let van = ma.getMonth() === zo.getMonth() ? String(ma.getDate()) : ma.toLocaleDateString("nl-NL", kort);
    if (ma.getFullYear() !== zo.getFullYear()) van += " " + ma.getFullYear();
    return "week " + weeknummer(ma) + " · " + van + " – " + zo.toLocaleDateString("nl-NL", kort) + " " + zo.getFullYear();
  }

  let wacht = null;
  function kopBijwerken() {
    if (titel) titel.textContent = kopTekst();
  }
  // Na een sprong de kop van het doel niet meteen overschrijven door de
  // scroll-meldingen van de vloeiende beweging ernaartoe.
  let sprong = 0;
  // Het laatste doel van de pijlen. Daar rekent de volgende klik van verder,
  // ook als het bord er nog heen aan het scrollen is, of aan het eind van
  // het jaar niet verder kán (dan zou je anders nooit december uit komen).
  // Wie zelf scrolt, wist het.
  let doelNu = null;
  scroller.addEventListener("scroll", function () {
    clearTimeout(wacht);
    wacht = setTimeout(function () {
      if (Date.now() - sprong > 800) {
        doelNu = null;
        kopBijwerken();
      }
    }, 60);
  });
  document.querySelectorAll("[data-zoom]").forEach(function (knop) {
    knop.addEventListener("click", function () {
      doelNu = null;
      setTimeout(kopBijwerken, 0);
    });
  });

  function volgende(d, richting) {
    const z = zoom();
    const nieuw = new Date(d);
    if (z === "dag") {
      nieuw.setDate(nieuw.getDate() + richting);
      return nieuw;
    }
    if (z === "week") {
      const ma = maandag(d);
      // Staat er nog geen maandag links (midden in een week), dan eerst
      // naar de maandag van deze week terug in plaats van een hele week.
      if (richting < 0 && ma.getTime() !== d.getTime()) return ma;
      ma.setDate(ma.getDate() + 7 * richting);
      return ma;
    }
    if (richting < 0 && d.getDate() !== 1) return new Date(d.getFullYear(), d.getMonth(), 1);
    return new Date(d.getFullYear(), d.getMonth() + richting, 1);
  }

  pijlen.forEach(function (pijl) {
    pijl.addEventListener("click", function (e) {
      const doel = volgende(doelNu || eersteInBeeld(), Number(pijl.dataset.blader));
      e.preventDefault();
      sprong = Date.now();
      doelNu = doel;
      if (naar(doel, true)) {
        // Meteen de kop van het doel tonen, niet pas na het scrollen.
        if (titel) titel.textContent = kopTekst(doel);
      } else {
        // Buiten dit jaar: dat jaar laden, op die dag.
        const url = new URL(window.location.href);
        url.searchParams.set("dag", iso(doel));
        url.searchParams.set("blader", "1");
        window.location.href = url.toString();
      }
    });
  });

  // Na het openen van de pagina (werkplanning.js / mijn-aanwezigheid.js
  // scrollen dan naar vandaag of de gekozen dag) de kop goed zetten.
  // Gebladerd naar een ander jaar (?blader=1): precies op die dag openen in
  // plaats van twee dagen ervoor, zoals bij een gewoon bezoek.
  function bijOpenen() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("blader") && params.get("dag")) naar(datum(params.get("dag")), false);
    kopBijwerken();
  }
  window.addEventListener("load", function () { setTimeout(bijOpenen, 0); });
})();
