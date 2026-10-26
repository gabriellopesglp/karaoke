// Persistência simples em localStorage (JSON), igual ao `store` do legado.
// As chaves são compartilhadas com o app legado (stem:<label>, pitch:<folder>,
// offset:<folder>, lyricScale, darkenBg, focusMode, wordSync, sessionId, queue).
export const store = {
  get(k, d) {
    try {
      const v = localStorage.getItem(k);
      return v === null ? d : JSON.parse(v);
    } catch (e) {
      return d;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch (e) {}
  },
};

// Normaliza para busca: minúsculas e sem acentos (todas as palavras precisam
// aparecer, em qualquer ordem).
export const norm = (s) =>
  String(s ?? "")
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .toLowerCase();
