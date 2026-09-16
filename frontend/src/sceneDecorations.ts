import type { Character, SceneDecorations, SceneSpaceEntry } from "./types";

export type ResolvedSceneDecorations = Omit<SceneDecorations, "leftMenu"> & {
  leftMenu: SceneSpaceEntry[];
};

function fallbackLinks(): SceneSpaceEntry[] {
  return [
    {
      text: "相册",
      icon: "Images",
      iconPosition: "end",
      action: "album",
      dividerWidth: 56,
    },
    {
      text: "与{name}的回忆",
      icon: "Heart",
      iconPosition: "start",
      action: "history",
      offsetX: -1,
      dividerWidth: 86,
    },
    {
      text: "她的小世界",
      icon: "Sparkles",
      iconPosition: "end",
      action: "profile",
      offsetX: 1,
      dividerWidth: 72,
    },
  ];
}

export function resolveSceneDecorations(
  character: Character,
): ResolvedSceneDecorations {
  const configured = character.sceneDecorations;
  if (!configured)
    return {
      avatarNote: { text: "一直在这里。", opacity: 0.56 },
      leftMenu: fallbackLinks(),
      signature: {
        text: "欢迎回来。",
        rotate: -2,
        opacity: 0.76,
        fontStyle: "handwritten",
        indent: 16,
      },
    };

  return {
    ...configured,
    leftMenu: configured.leftMenu?.length
      ? configured.leftMenu
      : fallbackLinks(),
  };
}

export function formatSceneDecorationText(text: string, character: Character) {
  return text.replaceAll("{name}", character.name);
}
