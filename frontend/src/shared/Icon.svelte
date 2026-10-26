<script>
  // Ícones SVG inline (sem biblioteca). Mesmo traço dos ícones da TV.
  let { name, size = 22 } = $props();
</script>

<svg
  class="ico"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden="true"
>
  {#if name === "play"}
    <path d="M8 5v14l11-7z" fill="currentColor" stroke="none" />
  {:else if name === "pause"}
    <rect x="6.5" y="5" width="3.5" height="14" rx="1" fill="currentColor" stroke="none" />
    <rect x="14" y="5" width="3.5" height="14" rx="1" fill="currentColor" stroke="none" />
  {:else if name === "prev"}
    <path d="M18 5.5v13l-9-6.5z" fill="currentColor" stroke="none" />
    <path d="M6 5.5v13" />
  {:else if name === "next"}
    <path d="M6 5.5v13l9-6.5z" fill="currentColor" stroke="none" />
    <path d="M18 5.5v13" />
  {:else if name === "search"}
    <circle cx="11" cy="11" r="6.5" />
    <path d="m16 16 4 4" />
  {:else if name === "queue"}
    <path d="M4 6h16M4 10h16M4 14h10" />
    <path d="M17.5 14.5v5M20 17h-5" />
  {:else if name === "tune"}
    <path d="M4 8h10M18 8h2M4 16h4M12 16h8" />
    <circle cx="16" cy="8" r="2.2" />
    <circle cx="10" cy="16" r="2.2" />
  {:else if name === "plus"}
    <path d="M12 5.5v13M5.5 12h13" />
  {:else if name === "minus"}
    <path d="M5.5 12h13" />
  {:else if name === "check"}
    <path d="m5.5 12.5 4 4 9-9" />
  {:else if name === "x"}
    <path d="M6 6l12 12M18 6 6 18" />
  {:else if name === "up"}
    <path d="m6 14 6-6 6 6" />
  {:else if name === "down"}
    <path d="m6 10 6 6 6-6" />
  {:else if name === "download"}
    <path d="M12 4v11M7.5 11 12 15.5 16.5 11" />
    <path d="M4.5 19.5h15" />
  {:else if name === "note"}
    <path d="M9 18V6l10-2v11.5" />
    <circle cx="6.8" cy="18" r="2.4" />
    <circle cx="16.8" cy="15.5" r="2.4" />
  {:else if name === "vol"}
    <path d="M11 5 6.5 9H3.5v6h3L11 19z" />
    <path d="M15.5 9a4.5 4.5 0 0 1 0 6M18.5 6a8.5 8.5 0 0 1 0 12" />
  {:else if name === "mute"}
    <path d="M11 5 6.5 9H3.5v6h3L11 19z" />
    <path d="m16 9.5 5 5M21 9.5l-5 5" />
  {:else if name === "mic"}
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21M8.5 21h7" />
  {:else if name === "moon"}
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  {:else if name === "focus"}
    <path d="M4 8V4h4M20 8V4h-4M4 16v4h4M20 16v4h-4M8 12h8" />
  {:else if name === "alert"}
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7.5V13M12 16.5v.01" />
  {:else if name === "refresh"}
    <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4.5v4.5H15" />
  {:else if name === "voices"}
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M21.5 20a6.5 6.5 0 0 0-4-6" />
  {:else if name === "phone"}
    <rect x="6.5" y="2.5" width="11" height="19" rx="2.5" />
    <path d="M10.5 18h3" />
  {:else if name === "expand"}
    <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
  {:else if name === "shrink"}
    <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
  {:else if name === "menu"}
    <path d="M4 7h16M4 12h16M4 17h16" />
  {:else if name === "power"}
    <path d="M12 3.5v8" />
    <path d="M6.7 6.6a7.5 7.5 0 1 0 10.6 0" />
  {:else if name === "trash"}
    <path d="M4 7h16M9 7V4h6v3M6.5 7l.8 12.5a1 1 0 0 0 1 .9h7.4a1 1 0 0 0 1-.9L17.5 7" />
  {:else if name === "disc"}
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="2.5" />
  {:else if name === "lyrics"}
    <path d="M4 6.5h11M4 11.5h11M4 16.5h7" />
    <path d="M19 5v9.5" />
    <circle cx="17.2" cy="15.8" r="1.9" />
  {:else if name === "remote"}
    <rect x="7" y="2" width="10" height="20" rx="2" />
    <circle cx="12" cy="7" r="1.5" />
    <path d="M10 12h4M12 10v4" />
  {:else if name === "sync"}
    <path d="M21 12a9 9 0 0 1-15.5 6.3L3 16" />
    <path d="M3 12a9 9 0 0 1 15.5-6.3L21 8" />
    <path d="M21 4v4h-4" />
    <path d="M3 20v-4h4" />
  {:else if name === "settings"}
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
  {:else if name === "score"}
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 3" />
  {/if}
</svg>

<style>
  .ico {
    flex: none;
    display: inline-block;
    vertical-align: middle;
  }
</style>
