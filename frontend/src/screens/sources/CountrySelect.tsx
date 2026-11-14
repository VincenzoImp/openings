import { Select } from "../../ui/Field";
import { COUNTRIES } from "./model";

/** The country of a search, by name; empty is "No country". */
export function CountrySelect({
  value,
  onChange,
  required = false,
}: {
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}) {
  return (
    <Select value={value} onChange={(event) => onChange(event.target.value)}>
      <option value="">{required ? "Choose a country" : "No country"}</option>
      {COUNTRIES.map(([country, label]) => (
        <option key={country} value={country}>
          {label}
        </option>
      ))}
    </Select>
  );
}
