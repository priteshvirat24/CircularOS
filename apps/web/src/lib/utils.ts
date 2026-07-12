import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { format, parseISO } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  try {
    const date = parseISO(dateString);
    return format(date, "MMM d, yyyy h:mm a");
  } catch (error) {
    return dateString;
  }
}

export function formatShortDate(dateString: string | null | undefined): string {
  if (!dateString) return "N/A";
  try {
    const date = parseISO(dateString);
    return format(date, "MMM d, yyyy");
  } catch (error) {
    return dateString;
  }
}
