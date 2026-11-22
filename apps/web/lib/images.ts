import credits from "./image-credits.json";

export type Credit = {
  file: string;
  title: string;
  author: string;
  license: string;
  license_url: string;
  source: string;
};

export type Photo = { src: string; credit: Credit };

const CREDITS = credits as Record<string, Credit>;

/** First key in the list that was actually downloaded. */
export function pick(...keys: string[]): Photo | null {
  for (const key of keys) {
    const credit = CREDITS[key];
    if (credit) return { src: credit.file, credit };
  }
  return null;
}

export function altFor(photo: Photo | null, fallback: string): string {
  if (!photo) return fallback;
  return `${fallback}. Photo: ${photo.credit.author}, ${photo.credit.license}`;
}

const CATEGORY: Record<string, string[]> = {
  museum: ["dubai-museum", "al-fahidi-historical-neighbourhood", "heritage-village"],
  mosque: ["jumeirah-mosque"],
  market: ["gold-souk", "spice-souk", "souk-al-bahar", "souk-madinat-jumeirah"],
  beach: ["jumeirah-beach", "jbr-beach"],
  park: ["zabeel-park", "safa-park", "dubai-miracle-garden", "al-qudra-lakes"],
  mall: ["the-dubai-mall", "mall-of-the-emirates", "deira-city-centre"],
  theme_park: ["img-worlds-of-adventure", "legoland-dubai", "motiongate-dubai", "aquaventure-waterpark"],
  water_park: ["aquaventure-waterpark", "wild-wadi-waterpark"],
  wildlife: ["ras-al-khor-wildlife-sanctuary", "al-qudra-lakes"],
  gallery: ["alserkal-avenue", "museum-of-the-future"],
  transit: ["dubai-creek-abra-crossing", "dubai-creek", "dhow-creek"],
  viewpoint: ["burj-khalifa", "dubai-frame", "downtown-dubai"],
  landmark: ["downtown-dubai", "burj-al-arab", "emirates-towers"],
};

const AREA: Record<string, string[]> = {
  "Old Dubai": ["al-fahidi-historical-neighbourhood", "gold-souk", "dubai-creek"],
  "Dubai Creek": ["dubai-creek", "dhow-creek", "al-seef"],
  Downtown: ["downtown-dubai", "burj-khalifa", "dubai-fountain"],
  "Marina / JBR": ["dubai-marina", "jbr-beach", "jumeirah-beach"],
  Palm: ["palm-jumeirah", "aquaventure-waterpark"],
  Jumeirah: ["jumeirah-beach", "jumeirah-mosque", "burj-al-arab"],
  "Business Bay": ["dubai-water-canal", "downtown-dubai"],
  "Al Quoz": ["alserkal-avenue", "dubai-water-canal"],
  Dubailand: ["global-village", "dubai-miracle-garden", "img-worlds-of-adventure"],
};

/**
 * Photo for a catalog place. Exact photo first, then something of the same kind,
 * then the same neighbourhood. Returns null when nothing relevant was downloaded
 * so the card shows a plain tile instead of a wrong landmark.
 */
export function photoForPlace(placeId?: string | null, category?: string | null, area?: string | null): Photo | null {
  if (placeId) {
    const exact = pick(placeId.replace(/^place-/, ""));
    if (exact) return exact;
  }
  if (category && CATEGORY[category]) {
    const byKind = pick(...CATEGORY[category]);
    if (byKind) return byKind;
  }
  if (area && AREA[area]) return pick(...AREA[area]);
  return null;
}

export function photoForArea(area?: string | null): Photo | null {
  return area && AREA[area] ? pick(...AREA[area]) : null;
}

/** Landing page imagery. Each list is a preference order. */
export const HERO = () => pick("hero-skyline", "burj-khalifa", "downtown-dubai");
export const CLOSING = () => pick("dubai-marina", "palm-jumeirah", "downtown-dubai");

export type Interest = { id: string; label: string; blurb: string; keys: string[] };

export const INTERESTS: Interest[] = [
  { id: "iconic", label: "Iconic Dubai", blurb: "Burj Khalifa, Downtown and the Fountain", keys: ["burj-khalifa", "downtown-dubai"] },
  { id: "culture", label: "Culture & Heritage", blurb: "Al Fahidi, museums and old quarters", keys: ["al-fahidi-historical-neighbourhood", "dubai-museum", "heritage-village", "jumeirah-mosque", "al-seef", "dubai-creek"] },
  { id: "desert", label: "Desert Adventures", blurb: "Dunes and conservation drives", keys: ["desert", "desert-dunes", "al-qudra-lakes"] },
  { id: "beaches", label: "Beaches & Relaxation", blurb: "Jumeirah and JBR shoreline", keys: ["jumeirah-beach", "jbr-beach"] },
  { id: "food", label: "Food & Local Flavors", blurb: "Souks and Emirati tables", keys: ["spice-souk", "emirati-food", "souk-madinat-jumeirah"] },
  { id: "family", label: "Family Fun", blurb: "Waterparks, parks and theme parks", keys: ["aquaventure-waterpark", "legoland-dubai", "wild-wadi-waterpark"] },
  { id: "shopping", label: "Shopping & Entertainment", blurb: "Malls, souks and promenades", keys: ["the-dubai-mall", "gold-souk", "mall-of-the-emirates"] },
  { id: "architecture", label: "Architecture & Museums", blurb: "Museum of the Future and skyline icons", keys: ["museum-of-the-future", "burj-al-arab", "dubai-frame", "downtown-dubai", "burj-khalifa"] },
  { id: "luxury", label: "Luxury Experiences", blurb: "Palm, Burj Al Arab and skyline views", keys: ["burj-al-arab", "palm-jumeirah"] },
  { id: "hidden", label: "Hidden Gems", blurb: "Quieter corners beyond the headline sights", keys: ["alserkal-avenue", "ras-al-khor-wildlife-sanctuary", "al-seef"] },
];

export function photoForInterest(id: string): Photo | null {
  const row = INTERESTS.find((item) => item.id === id);
  return row ? pick(...row.keys) : null;
}

/** All distinct credits for the footer. */
export function allCredits(): Credit[] {
  const seen = new Set<string>();
  return Object.values(CREDITS)
    .filter((c) => (seen.has(c.file) ? false : (seen.add(c.file), true)))
    .sort((a, b) => a.title.localeCompare(b.title));
}
