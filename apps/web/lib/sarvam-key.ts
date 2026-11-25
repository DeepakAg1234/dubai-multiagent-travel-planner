import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

/** Pull `SARVAM_API_KEY` out of env-file text. Other names are ignored. */
export function sarvamKeyFromText(text: string): string {
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1 || trimmed.slice(0, eq).trim() !== "SARVAM_API_KEY") continue;
    let value = trimmed.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    return value.trim();
  }
  return "";
}

/**
 * The web process may not see the repo-root `.env`, which is where local keys live.
 * Bracket access avoids a build-time inline of a missing key. Only this name is copied.
 */
export function sarvamKey(): string {
  const current = process.env["SARVAM_API_KEY"]?.trim();
  if (current) return current;
  const candidates = [path.join(process.cwd(), ".env"), path.join(process.cwd(), "..", "..", ".env")];
  for (const file of candidates) {
    if (!existsSync(file)) continue;
    const value = sarvamKeyFromText(readFileSync(file, "utf8"));
    if (!value) continue;
    process.env["SARVAM_API_KEY"] = value;
    return value;
  }
  return "";
}
