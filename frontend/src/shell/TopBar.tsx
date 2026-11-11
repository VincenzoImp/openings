import { Button, IconButton } from "../design";
import type { Density, Theme } from "./preferences";
import { SCREENS, destinationOf } from "./routes";

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
  const group = destination?.group;
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
          {destination?.item.label ?? SCREENS[route]}
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
