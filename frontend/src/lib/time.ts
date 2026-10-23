const DAY_MS = 86_400_000;

const relativeFormat = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const shortDate = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const monthYear = new Intl.DateTimeFormat(undefined, { month: "long", year: "numeric" });
export const fullDateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "full", timeStyle: "short" });

const startOfDay = (date: Date) => new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();

/** Heading for the group an entry belongs to: Today, Yesterday, This week, or its month. */
export function dateGroup(date: Date, now = new Date()): string {
  const days = Math.round((startOfDay(now) - startOfDay(date)) / DAY_MS);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return "This week";
  return monthYear.format(date);
}

export function relativeTime(date: Date, now = new Date()): string {
  const seconds = Math.round((date.getTime() - now.getTime()) / 1000);
  if (seconds > -60) return "Just now";
  if (seconds > -3600) return relativeFormat.format(Math.round(seconds / 60), "minute");
  if (seconds > -86_400) return relativeFormat.format(Math.round(seconds / 3600), "hour");
  if (seconds > -7 * 86_400) return relativeFormat.format(Math.round(seconds / 86_400), "day");
  return shortDate.format(date);
}
