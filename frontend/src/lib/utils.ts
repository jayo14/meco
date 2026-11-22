import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatUsd(val: number | null | undefined, fallback: string = "--"): string {
  if (val === null || val === undefined) return fallback;
  if (Math.abs(val) >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (Math.abs(val) >= 1_000) return `$${(val / 1_000).toFixed(1)}k`;
  if (Math.abs(val) < 0.0001 && val !== 0) return `$${val.toExponential(2)}`;
  if (Math.abs(val) < 0.01) return `$${val.toFixed(6)}`;
  return `$${val.toFixed(2)}`;
}

export function formatPct(val: number | null | undefined, fallback: string = "--"): string {
  if (val === null || val === undefined) return fallback;
  return `${val >= 0 ? "+" : ""}${val.toFixed(1)}%`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "--";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

export function truncateMint(mint: string, chars: number = 4): string {
  if (!mint || mint.length <= chars * 2 + 2) return mint;
  return `${mint.slice(0, chars)}...${mint.slice(-chars)}`;
}
