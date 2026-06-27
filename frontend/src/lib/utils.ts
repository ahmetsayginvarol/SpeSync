import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format } from 'date-fns'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function todayIso(cutoffHour = 4): string {
  const now = new Date()
  if (now.getHours() < cutoffHour) {
    // Before cutoff — still "yesterday" for ordering purposes
    now.setDate(now.getDate() - 1)
  }
  return format(now, 'yyyy-MM-dd')
}

export function tomorrowIso(cutoffHour = 4): string {
  const now = new Date()
  const base = now.getHours() < cutoffHour ? now : new Date(now.getTime() + 86_400_000)
  return format(base, 'yyyy-MM-dd')
}
