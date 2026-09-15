import type { Character } from "./types";

/** Keep old character packs compatible while exposing semantic design tokens. */
export function themeStyle(character?: Character) {
  const source = character?.theme || {};
  const primary = source.primary || source.accent || "#68615f";
  const secondary = source.secondary || source.soft || "#eee9e4";
  const text = source.text || source.ink || "#302c32";
  return {
    ...Object.fromEntries(
      Object.entries(source).map(([key, value]) => [`--${key}`, value]),
    ),
    "--primary": primary,
    "--accent": source.accent || primary,
    "--secondary": secondary,
    "--soft": source.soft || secondary,
    "--background": source.background || "#faf8f5",
    "--surface": source.surface || "#ffffffb8",
    "--glass-surface": "rgba(255, 255, 255, 0.52)",
    "--glass-surface-strong": "rgba(255, 255, 255, 0.61)",
    "--text": text,
    "--ink": text,
    "--muted": source.muted || "#746b75",
  };
}
