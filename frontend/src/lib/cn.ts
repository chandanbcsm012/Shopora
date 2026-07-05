/** Joins truthy class names. Avoids the `${a} ${b && c}` string-splicing
 * that tends to leak stray whitespace/`false`/`undefined` into className. */
export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
