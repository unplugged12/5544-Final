/** Turn a snake_case enum value into a space-separated string for display. */
export function formatEnumValue(value) {
  if (!value) return "";
  return String(value).replace(/_/g, " ");
}
