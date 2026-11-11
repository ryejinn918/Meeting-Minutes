export function formatMeetingDate(value: string) {
  return new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", weekday: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(value));
}

export function formatDueDate(value: string | null) {
  if (!value) return "미정";
  return new Intl.DateTimeFormat("ko-KR", { month: "short", day: "numeric" }).format(new Date(`${value}T00:00:00`));
}

export function formatFileSize(bytes: number) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

