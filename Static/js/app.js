// Sofort ausgeführte Funktion (IIFE), damit nichts in den globalen Scope kommt
(() => {
  // Kleiner Helfer: statt document.querySelector(...) immer nur $(...)
  const $ = (sel) => document.querySelector(sel);

  // Warten, bis das DOM komplett geladen ist
  document.addEventListener("DOMContentLoaded", () => {
    /* ============================================================
     *  DOM ELEMENTE AUS DEM HTML SUCHEN
     * ============================================================ */
    const accBtn      = $("#ping");        // Avatar-Button oben links
    const box         = $("#box");         // Dropdown-Box unter dem Avatar
    const list        = $("#chat-list");   // Liste der Chats in der Sidebar
    const plus        = $("#new-chat");    // Button "Neuer Chat"
    const sidebar     = $(".sidebar");     // Sidebar-Container
    const settingsBtn = $("#colour");      // Button für Theme-Einstellungen
    const inputEl     = $("#schreiben");   // Text-Eingabefeld im Chat
    const chatbox     = $(".chatbox");     // Bereich, in dem Nachrichten angezeigt werden

    // Wenn essentielle Elemente fehlen, beende das Skript
    if (!list || !sidebar) return;

    /* ============================================================
     *  STATE VARIABLEN (AKTUELLER ZUSTAND)
     * ============================================================ */
    let activeChatId  = null; // Welcher Chat ist gerade ausgewählt?
    let currentChatId = null; // Für Kontextmenü (Rename/Delete)
    let currentChatEl = null; // Das DOM-Element des aktuell im Menü bearbeiteten Chats

    /* ============================================================
     *  INLINE-MENÜS ENTFERNEN (FALLS NOCH VORHANDEN)
     * ============================================================ */
    // Falls im HTML noch alte Inline-Menüs existieren, löschen wir sie
    list.querySelectorAll(".chat-item .menu").forEach(m => m.remove());

    /* ============================================================
     *  NACHRICHTENBEREICH INITIALISIEREN
     * ============================================================ */

    // Stellt sicher, dass es ein <div id="messages"> gibt
    function ensureMessagesContainer() {
      let el = document.getElementById("messages");
      if (!el && chatbox) {
        el = document.createElement("div");
        el.id = "messages";
        el.className = "messages";
        chatbox.appendChild(el);
      }
      return el;
    }
    const messagesEl = ensureMessagesContainer();

    // Nachrichten im UI leeren, z.B. wenn Chat gewechselt wird
    function clearMessagesUI() {
      messagesEl.innerHTML = "";
      messagesEl.dataset.chatId = activeChatId ? String(activeChatId) : "";
    }

    // Eine Nachricht (User oder Bot) im Chat anzeigen
    function renderMessage(text, isBot = false) {
      // Sicherheitscheck: nur anzeigen, wenn noch der gleiche Chat aktiv ist
      if (messagesEl.dataset.chatId && messagesEl.dataset.chatId !== String(activeChatId || "")) return;

      const b = document.createElement("div");
      b.className = isBot ? "msg msg-in" : "msg msg-out";
      
      if (isBot) {
        // Bot-Nachricht mit Emoji links und Text daneben
        b.innerHTML = `<span class="bot-emoji">🤖</span><span class="msg-text">${text}</span>`;
      } else {
        // User-Nachricht nur als Text
        b.textContent = text;
      }
      
      messagesEl.appendChild(b);
      messagesEl.scrollTop = messagesEl.scrollHeight; // Immer nach unten scrollen
      return b;
    }

    // "Denkt nach..."-Blase des Bots anzeigen
    function renderThinkingIndicator() {
      // Wieder Sicherheitscheck: nur im richtigen Chat anzeigen
      if (messagesEl.dataset.chatId && messagesEl.dataset.chatId !== String(activeChatId || "")) return null;

      const thinkDiv = document.createElement("div");
      thinkDiv.className = "msg msg-in msg-thinking";
      thinkDiv.innerHTML = `
        <span class="bot-emoji">🤖</span>
        <div class="thinking-content">
          <div class="thinking-animation">
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
            <span class="thinking-dot"></span>
          </div>
          <span class="thinking-text">KiBot denkt nach...</span>
        </div>
      `;
      messagesEl.appendChild(thinkDiv);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return thinkDiv;
    }

    // "Denkt nach..."-Blase wieder entfernen
    function removeThinkingIndicator(thinkDiv) {
      if (thinkDiv && thinkDiv.parentNode) {
        thinkDiv.remove();
      }
    }

    /* ============================================================
     *  AVATAR-MENÜ (PROFIL / LOGOUT ETC.)
     * ============================================================ */
    if (accBtn && box) {
      // Avatar anklicken → Box ein-/ausblenden
      accBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        box.classList.toggle("hidden");
        list && list.classList.toggle("avatar-open", !box.classList.contains("hidden"));
      });

      // Klick irgendwo anders → Box schließen
      document.addEventListener("click", (e) => {
        if (!box.classList.contains("hidden") && !box.contains(e.target) && e.target !== accBtn) {
          box.classList.add("hidden");
          list && list.classList.remove("avatar-open");
        }
      });
    }

    /* ============================================================
     *  KONTEXTMENÜ FÜR CHATS (RECHTSKLICK/MEHR-BUTTON)
     * ============================================================ */

    // Ein zentrales Kontextmenü für die Chats in der Sidebar
    const globalMenu = document.createElement("ul");
    globalMenu.id = "chat-menu";
    globalMenu.className = "menu hidden";
    sidebar.appendChild(globalMenu);

    // Kontextmenü schließen
    function closeMenu() {
      globalMenu.classList.add("hidden");
      delete globalMenu.dataset.forId;
      currentChatId = null;
      currentChatEl = null;
    }

    // Inhalt des Kontextmenüs (Titel + Aktionen) setzen
    function buildMenu(title) {
      globalMenu.innerHTML = `
        <li><h3><strong>${title}</strong></h3></li>
        <li data-action="rename">Umbenennen</li>
        <li data-action="delete">Löschen</li>
      `;
    }

    // Klick irgendwo außerhalb → Kontextmenü schließen
    document.addEventListener("click", (e) => {
      if (!e.target.closest("#chat-menu") && !e.target.closest(".more")) {
        closeMenu();
      }
    });

    /* ============================================================
     *  CHAT ÖFFNEN (NACHRICHTEN LADEN)
     * ============================================================ */

    // Hilfsfunktion zum Öffnen eines Chats anhand des Sidebar-Elements
    async function openChatByElement(item) {
      if (!item) return;
      const chatId = item.dataset.id;
      if (!chatId) return;

      activeChatId = chatId;

      // alten "active"-Status entfernen, neuen setzen
      list.querySelectorAll(".chat-item.active").forEach(el => el.classList.remove("active"));
      item.classList.add("active");

      clearMessagesUI();

      try {
        const r = await fetch(`/api/chats/${chatId}/messages`, { headers: { Accept: "application/json" } });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data?.error || "Fehler beim Laden");
        
        // Jede Nachricht anzeigen, Bot oder User je nach user_id
        (data.messages || []).forEach(m => {
          const isBot = m.user_id === 0; // user_id 0 = Bot/KI
          renderMessage(m.content, isBot);
        });
      } catch (err) {
        console.error(err);
        Swal.fire({ icon: "error", title: "Fehler", text: "Nachrichten konnten nicht geladen werden." });
      }
    }

    /* ============================================================
     *  CHATS VOM SERVER LADEN UND SIDEBAR AUFBAUEN
     * ============================================================ */

    fetch("/api/chats")
      .then((r) => r.json())
      .then(async (d) => {
        if (!d.chats || d.chats.length === 0) return;
        list.innerHTML = "";

        d.chats.forEach((chat) => {
          const item = document.createElement("div");
          item.className = "chat-item";
          item.dataset.id = chat.id;

          const title = document.createElement("span");
          title.className = "title";
          title.textContent = chat.title;

          const more = document.createElement("button");
          more.className = "more";
          more.setAttribute("aria-label", "Mehr");
          more.textContent = "⋯";

          item.appendChild(title);
          item.appendChild(more);
          list.appendChild(item);
        });

        // Ersten Chat automatisch öffnen
        const firstItem = list.querySelector(".chat-item");
        if (firstItem) await openChatByElement(firstItem);
      })
      .catch((err) => console.error("Fehler beim Laden der Chats:", err));

    /* ============================================================
     *  NEUEN CHAT ANLEGEN
     * ============================================================ */
    if (plus) {
      plus.addEventListener("click", async () => {
        try {
          const r = await fetch("/api/chats", { method: "POST" });
          const data = await r.json().catch(() => null);
          if (!r.ok) throw new Error(data?.error || "Fehler beim Erstellen des Chats.");

          const item = document.createElement("div");
          item.className = "chat-item";
          item.dataset.id = data.id;

          const title = document.createElement("span");
          title.className = "title";
          title.textContent = data.title || "Neuer Chat";

          const more = document.createElement("button");
          more.className = "more";
          more.setAttribute("aria-label", "Mehr");
          more.textContent = "⋯";

          item.appendChild(title);
          item.appendChild(more);
          list.prepend(item); // Neuen Chat oben in die Liste packen

          await openChatByElement(item);
        } catch (err) {
          console.error("Fehler beim Erstellen des Chats:", err);
          Swal.fire({ icon: "error", title: "Fehler", text: "Neuer Chat konnte nicht erstellt werden." });
        }
      });
    }

    /* ============================================================
     *  KLICKS AUF DIE CHAT-LISTE (CHAT WECHSELN)
     * ============================================================ */

    // Klick auf Chat-Namen → Chat öffnen
    list.addEventListener("click", async (e) => {
      if (e.target.closest(".more")) return; // Menü-Button wird separat behandelt
      const item = e.target.closest(".chat-item");
      if (!item) return;
      await openChatByElement(item);
    });

    // Klick auf "..."-Button → Kontextmenü öffnen
    list.addEventListener("click", (e) => {
      const btn = e.target.closest(".more");
      if (!btn) return;
      e.stopPropagation();

      const chat = btn.closest(".chat-item");
      if (!chat) return;

      const chatId = chat.dataset.id;
      if (!chatId) return;

      currentChatId = chatId;
      currentChatEl = chat;

      const titleEl = chat.querySelector(".title");
      const chatTitle = titleEl ? titleEl.textContent : "Chat";
      buildMenu(chatTitle);

      // Wenn Menü schon offen ist und denselben Chat hat → schließen
      if (!globalMenu.classList.contains("hidden") && globalMenu.dataset.forId === currentChatId) {
        closeMenu();
        return;
      }

      globalMenu.dataset.forId = currentChatId;
      globalMenu.classList.remove("hidden");
    });

    /* ============================================================
     *  KONTEXTMENÜ-AKTIONEN: CHAT LÖSCHEN / UMBENENNEN
     * ============================================================ */

    globalMenu.addEventListener("click", async (e) => {
      const li = e.target.closest("li");
      if (!li) return;
      const action = li.dataset.action;
      if (!action) return;

      const menuChatId = globalMenu.dataset.forId || currentChatId;
      
      if (!menuChatId) {
        Swal.fire({ icon: "error", title: "Fehler", text: "Chat-ID nicht gefunden." });
        return;
      }

      /* ---------- CHAT LÖSCHEN ---------- */
      if (action === "delete") {
        const { isConfirmed } = await Swal.fire({
          title: "Chat löschen?",
          text: "Möchtest du diesen Chat wirklich löschen?",
          icon: "warning",
          showCancelButton: true,
          confirmButtonText: "Ja, löschen",
          cancelButtonText: "Abbrechen",
          confirmButtonColor: "#e53935"
        });
        if (!isConfirmed) return;

        try {
          const r = await fetch(`/api/chats/${menuChatId}`, { 
            method: "DELETE", 
            headers: { Accept: "application/json" } 
          });
          
          if (!r.ok) {
            const data = await r.json().catch(() => ({}));
            throw new Error(data?.error || "Löschen fehlgeschlagen.");
          }

          const el = document.querySelector(`[data-id="${menuChatId}"]`);
          const removedWasActive = (menuChatId === activeChatId);
          
          if (el && el.parentNode) {
            el.remove();
          }
          
          closeMenu();

          // Falls der aktuell offene Chat gelöscht wurde → anderen auswählen oder leeren
          if (removedWasActive) {
            const next = list.querySelector(".chat-item");
            if (next) {
              await openChatByElement(next);
            } else {
              activeChatId = null;
              clearMessagesUI();
            }
          }

          Swal.fire({ 
            icon: "success", 
            title: "Gelöscht", 
            timer: 900, 
            showConfirmButton: false 
          });
        } catch (err) {
          Swal.fire({ 
            icon: "error", 
            title: "Fehler", 
            text: err.message || "Technischer Fehler beim Löschen." 
          });
        }
      }

      /* ---------- CHAT UMBENENNEN ---------- */
      if (action === "rename") {
        const chatEl = document.querySelector(`[data-id="${menuChatId}"]`);
        if (!chatEl) {
          Swal.fire({ icon: "error", title: "Fehler", text: "Chat nicht gefunden." });
          return;
        }

        const titleEl = chatEl.querySelector(".title");
        const currentTitle = titleEl ? titleEl.textContent : "";

        const { value: newTitle, isConfirmed } = await Swal.fire({
          title: "Chat umbenennen",
          input: "text",
          inputValue: currentTitle,
          inputLabel: "Neuer Titel",
          showCancelButton: true,
          confirmButtonText: "Speichern",
          cancelButtonText: "Abbrechen",
          preConfirm: (val) => {
            const v = (val || "").trim();
            if (!v) return Swal.showValidationMessage("Titel darf nicht leer sein");
            if (v.length > 150) return Swal.showValidationMessage("Max. 150 Zeichen");
            if (v === currentTitle) return Swal.showValidationMessage("Titel unverändert");
            return v;
          }
        });
        
        if (!isConfirmed || !newTitle) return;

        try {
          const r = await fetch(`/api/chats/${menuChatId}`, {
            method: "PUT",
            headers: { 
              "Content-Type": "application/json", 
              "Accept": "application/json" 
            },
            body: JSON.stringify({ title: newTitle })
          });

          const responseText = await r.text();
          let data;
          
          try {
            data = JSON.parse(responseText);
          } catch (parseErr) {
            throw new Error("Server hat ungültige JSON gesendet");
          }

          if (!r.ok) {
            throw new Error(data?.error || `Server Fehler: ${r.status}`);
          }

          if (titleEl) {
            titleEl.textContent = data?.title || newTitle;
          }
          buildMenu(data?.title || newTitle);
          closeMenu();

          Swal.fire({ 
            icon: "success", 
            title: "Gespeichert", 
            timer: 900, 
            showConfirmButton: false 
          });
        } catch (err) {
          Swal.fire({ 
            icon: "error", 
            title: "Fehler", 
            text: err.message || "Technischer Fehler beim Umbenennen." 
          });
        }
      }
    });

    /* ============================================================
     *  ENTER DRÜCKEN → NACHRICHT SENDEN + KI-ANTWORT HOLEN
     * ============================================================ */
    if (inputEl && messagesEl) {
      inputEl.addEventListener("keydown", async (e) => {
        // Enter ohne Shift → Senden
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          const text = (inputEl.value || "").trim();
          if (!text) return;

          // Falls kein Chat aktiv ist → neuen Chat anlegen oder ersten öffnen
          if (!activeChatId) {
            const first = list.querySelector(".chat-item");
            if (first) {
              await openChatByElement(first);
            } else {
              const res = await Swal.fire({
                icon: "info",
                title: "Kein Chat ausgewählt",
                text: "Möchtest du einen neuen Chat erstellen?",
                showCancelButton: true,
                confirmButtonText: "Ja, erstellen",
                cancelButtonText: "Abbrechen"
              });
              if (!res.isConfirmed) return;

              try {
                const r = await fetch("/api/chats", { method: "POST" });
                const data = await r.json().catch(() => null);
                if (!r.ok || !data?.id) throw new Error(data?.error || "Fehler beim Erstellen.");

                const item = document.createElement("div");
                item.className = "chat-item";
                item.dataset.id = data.id;

                const title = document.createElement("span");
                title.className = "title";
                title.textContent = data.title || "Neuer Chat";

                const more = document.createElement("button");
                more.className = "more";
                more.textContent = "⋯";

                item.appendChild(title);
                item.appendChild(more);
                list.prepend(item);

                await openChatByElement(item);
              } catch (err) {
                Swal.fire({ icon: "error", title: "Fehler", text: err.message || "Chat konnte nicht erstellt werden." });
                return;
              }
            }
          }

          // User-Nachricht direkt im UI anzeigen
          messagesEl.dataset.chatId = String(activeChatId);
          renderMessage(text, false);
          inputEl.value = "";
          inputEl.disabled = true; // während die KI antwortet: Eingabe sperren

          // "Denkt nach..."-Anzeige einblenden
          const thinkingIndicator = renderThinkingIndicator();

          try {
            // Nachricht an Backend schicken
            const r = await fetch(`/api/chats/${activeChatId}/messages`, {
              method: "POST",
              headers: { "Content-Type": "application/json", "Accept": "application/json" },
              body: JSON.stringify({ content: text })
            });
            
            const data = await r.json().catch(() => ({}));
            
            if (!r.ok) {
              throw new Error(data?.error || `Fehler: ${r.status}`);
            }

            // "Denkt nach..." wieder entfernen
            removeThinkingIndicator(thinkingIndicator);

            // Bot-Antwort anzeigen, falls vorhanden
            if (data.bot_message && data.bot_message.content) {
              renderMessage(data.bot_message.content, true);
            }

          } catch (err) {
            console.error(err);
            removeThinkingIndicator(thinkingIndicator);
            Swal.fire({ 
              icon: "error", 
              title: "Fehler", 
              text: err.message || "Nachricht konnte nicht gesendet werden." 
            });
          } finally {
            inputEl.disabled = false; // Eingabe wieder aktivieren
            inputEl.focus();
          }
        }
      });
    }

    /* ============================================================
     *  THEME HANDLING (FARBE DER OBERFLÄCHE)
     * ============================================================ */

    // Theme-Klassen auf <body> anwenden
    function applyTheme(name) {
      const themes = ["pink", "blue", "dark"];
      document.body.classList.remove(...themes.map(t => `theme-${t}`));
      if (name && name !== "pink") document.body.classList.add(`theme-${name}`);
    }

    // Beim Laden: Theme vom Server holen
    (async () => {
      try {
        const r = await fetch("/api/farben", { method: "GET", headers: { Accept: "application/json" } });
        const data = await r.json().catch(() => ({}));
        applyTheme((r.ok && data?.theme) ? data.theme : "pink");
      } catch {
        applyTheme("pink");
      }
    })();

    // Klick auf Einstellungen (Theme wechseln)
    if (settingsBtn) {
      settingsBtn.addEventListener("click", async () => {
        // aktuelles Theme herausfinden
        const current = document.body.classList.contains("theme-blue")
          ? "blue"
          : document.body.classList.contains("theme-dark")
            ? "dark"
            : "pink";

        const { value: picked, isConfirmed } = await Swal.fire({
          title: "Einstellungen",
          html: `
            <div class="swatch-grid">
              <button type="button" class="swatch swatch-pink"  data-theme="pink"  aria-label="Pink"></button>
              <button type="button" class="swatch swatch-blue"  data-theme="blue"  aria-label="Blau"></button>
              <button type="button" class="swatch swatch-dark"  data-theme="dark"  aria-label="Dunkel"></button>
            </div>
            <p class="swatch-hint">Theme auswählen</p>
          `,
          showCancelButton: true,
          confirmButtonText: "Übernehmen",
          cancelButtonText: "Abbrechen",
          focusConfirm: false,
          width: 360,
          didOpen: () => {
            // Markiert die aktuell ausgewählte Farbe
            const container = Swal.getHtmlContainer();
            const grid = container.querySelector(".swatch-grid");
            const pre = grid.querySelector(`.swatch[data-theme="${current}"]`);
            if (pre) pre.classList.add("selected");
            grid.addEventListener("click", (e) => {
              const btn = e.target.closest(".swatch");
              if (!btn) return;
              grid.querySelectorAll(".swatch").forEach(s => s.classList.remove("selected"));
              btn.classList.add("selected");
            });
          },
          preConfirm: () => {
            const pick = Swal.getHtmlContainer().querySelector(".swatch.selected")?.getAttribute("data-theme");
            if (!pick) { Swal.showValidationMessage("Bitte ein Theme auswählen"); return false; }
            return pick;
          }
        });

        if (!isConfirmed || !picked) return;

        // Sofort im Frontend anwenden
        applyTheme(picked);

        // Und zusätzlich im Backend speichern
        try {
          const r = await fetch("/api/farben", {
            method: "POST",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            body: JSON.stringify({ theme: picked })
          });
          if (!r.ok) throw new Error("Speichern fehlgeschlagen");
          Swal.fire({ icon: "success", title: "Gespeichert", text: `Theme: ${picked}`, timer: 900, showConfirmButton: false });
        } catch {
          Swal.fire({ icon: "warning", title: "Nicht gespeichert", text: "Server konnte das Theme nicht speichern.", timer: 1400, showConfirmButton: false });
        }
      });
    }
  });
})();
