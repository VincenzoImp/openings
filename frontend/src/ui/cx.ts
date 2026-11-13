/** Class names joined, falsy values skipped. */
export function cx(...names: (string | false | null | undefined)[]) {
  return names.filter(Boolean).join(" ");
}
