/**
 * A minimal, dependency-free slugify used to auto-suggest a slug from a
 * name in the admin category/brand/product forms. Deliberately simple (no
 * unicode transliteration library) — good enough for a suggestion the user
 * can still edit before submit; the backend is the source of truth for
 * slug-uniqueness validation either way.
 */
export function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}
