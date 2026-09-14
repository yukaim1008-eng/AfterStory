/** Presentation-only excerpts: no inferred facts, generated summaries or invented dates. */
export function excerpt(value: string, length = 56) {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > length ? `${text.slice(0, length)}…` : text;
}
export function displayTime(value?: string | null) {
  if (!value || Number.isNaN(Date.parse(value))) return "未记录时间";
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
