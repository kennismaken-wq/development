{% autoescape off %}/* Service worker van de klusapp — wordt gerenderd door config/pwa.py.
   Bewust zuinig (zie development/PWA.md):
   - schermen komen altijd vers van de server; alleen zonder netwerk toont
     hij de offline-pagina. Zo staat er nooit een verlopen CSRF-token of
     andermans gegevens in de cache;
   - alleen bestanden onder /static/ gaan de cache in. Niets onder /media/,
     geen POST, geen /beheer/. */
var CACHE = "klusapp-{{ versie }}";
var OFFLINE = "{{ offline_url|escapejs }}";
var VOORAF = [OFFLINE{% for bestand in bestanden %}, "{{ bestand|escapejs }}"{% endfor %}];
// WhiteNoise zet in productie een hash in de naam (app.3f9c2a1b7d0e.css):
// zo'n bestand verandert nooit meer en mag direct uit de cache komen.
var GEHASHT = /\.[0-9a-f]{12}\.[a-z0-9]+$/;

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE).then(function (cache) {
      return cache.addAll(VOORAF);
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys().then(function (namen) {
      return Promise.all(namen.filter(function (naam) {
        return naam !== CACHE;
      }).map(function (naam) {
        return caches.delete(naam);
      }));
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (event) {
  var verzoek = event.request;
  if (verzoek.method !== "GET") return;
  var url = new URL(verzoek.url);
  if (url.origin !== self.location.origin) return;

  if (verzoek.mode === "navigate") {
    event.respondWith(
      fetch(verzoek).catch(function () {
        return caches.match(OFFLINE);
      })
    );
    return;
  }

  if (url.pathname.indexOf("/static/") !== 0) return;

  if (GEHASHT.test(url.pathname)) {
    event.respondWith(
      caches.match(verzoek).then(function (bewaard) {
        return bewaard || fetch(verzoek).then(function (antwoord) {
          if (antwoord.ok) {
            var kopie = antwoord.clone();
            caches.open(CACHE).then(function (cache) { cache.put(verzoek, kopie); });
          }
          return antwoord;
        });
      })
    );
  } else {
    // Lokaal (DEBUG) heeft niets een hash: dan eerst het netwerk, zodat een
    // aangepaste app.css meteen zichtbaar is, en de cache alleen als vangnet.
    event.respondWith(
      fetch(verzoek).catch(function () {
        return caches.match(verzoek);
      })
    );
  }
});

/* Pushmeldingen (pushberichten/versturen.py stuurt {titel, tekst, url}).
   iOS trekt het abonnement in als een push geen melding toont, dus er komt
   altijd een melding, ook als de inhoud onleesbaar is. */
self.addEventListener("push", function (event) {
  var bericht = {};
  try { bericht = event.data ? event.data.json() : {}; } catch (e) {}
  event.waitUntil(
    self.registration.showNotification(bericht.titel || "De Groene M", {
      body: bericht.tekst || "",
      icon: "{{ icoon|escapejs }}",
      data: { url: bericht.url || "/" },
    })
  );
});

// Tik op de melding: de app naar voren halen, of openen als hij dicht is.
self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var doel = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (vensters) {
      for (var i = 0; i < vensters.length; i++) {
        if ("focus" in vensters[i]) {
          vensters[i].navigate(doel);
          return vensters[i].focus();
        }
      }
      return self.clients.openWindow(doel);
    })
  );
});
{% endautoescape %}