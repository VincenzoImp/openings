import { Button, IconButton } from "../design";
import type { Density, Theme } from "./preferences";
import { HOME, SCREENS, destinationOf } from "./routes";

/** Where you are, what the workspace is doing, and the two display choices. */
export function TopBar({
  route,
  saving,
  onRefresh,
  theme,
  onTheme,
  density,
  onDensity,
  inert,
}: {
  route: string;
  saving: boolean;
  onRefresh: () => void;
  theme: Theme;
  onTheme: () => void;
  density: Density;
  onDensity: () => void;
  inert?: boolean;
}) {
  const destination = destinationOf(route);
  // The home screen says which day it is; the others say where they are.
  const today =
    route === HOME &&
    new Date().toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  const group = today ? "" : destination?.group;
  const otherTheme = theme === "light" ? "dark" : "light";
  const otherDensity = density === "compact" ? "comfortable" : "compact";
  return (
    <header className="topbar" inert={inert}>
      <p className="crumb muted grow">
        {group && (
          <>
            <span className="only-desktop">{group}</span>
            <span className="only-desktop" aria-hidden="true">
              /
            </span>
          </>
        )}
        <span aria-current="page">
          {today || (destination?.item.label ?? SCREENS[route])}
        </span>
      </p>
      {saving && (
        <span className="status" role="status">
          <span className="spinner" aria-hidden="true" />
          Saving…
        </span>
      )}
      <IconButton
        icon="refresh"
        label="Refresh workspace"
        onClick={onRefresh}
      />
      <Button
        type="button"
        variant="quiet"
        size="sm"
        icon={density === "compact" ? "compact" : "comfortable"}
        aria-label={`Density: ${density}. Switch to ${otherDensity}`}
        onClick={onDensity}
      >
        <span className="only-desktop">Density</span>
      </Button>
      <Button
        type="button"
        variant="quiet"
        size="sm"
        icon={theme === "light" ? "sun" : "moon"}
        aria-label={`Theme: ${theme}. Switch to ${otherTheme}`}
        onClick={onTheme}
      >
        <span className="only-desktop">Theme</span>
      </Button>
    </header>
  );
}
