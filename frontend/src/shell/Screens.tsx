import {
  Component,
  Suspense,
  lazy,
  type ComponentType,
  type ReactNode,
} from "react";
import { RotateCw } from "lucide-react";
import { Button } from "../ui/Button";
import { EmptyState, SkeletonRows } from "../ui/Page";
import { ROUTES, type RouteId } from "./routes";

// One module per screen, loaded when it is first opened (or when the pointer
// reaches its navigation item). A module default-exports a component without
// props; it reads its address with useRoute() and its data with Query hooks.
// A screen issue replaces one loader's target and nothing else.
type Module = Promise<{ default: ComponentType }>;
export const LOADERS: Record<RouteId, () => Module> = {
  today: () => import("../screens/today/Today"),
  jobs: () => import("../pages/Jobs"),
  applications: () => import("../pages/Applications"),
  application: () => import("../pages/Review"),
  profile: () => import("../screens/profile/Profile"),
  preferences: () => import("../pages/Preferences"),
  templates: () => import("../pages/Templates"),
  sources: () => import("../pages/Collection"),
  settings: () => import("../pages/Settings"),
  setup: () => import("../screens/setup/Setup"),
};

const SCREENS = Object.fromEntries(
  Object.entries(LOADERS).map(([id, load]) => [id, lazy(load)]),
) as unknown as Record<RouteId, ComponentType>;

/** Start loading a screen's code before it is opened. */
export function preload(id: RouteId) {
  void LOADERS[id]().catch(() => {
    // The screen reports the failure when it is opened.
  });
}

// The screens built before the design system keep their own frame until
// their issue rebuilds them (#222–#227); a rebuilt screen leaves this list.
const LEGACY = new Set<RouteId>([
  "jobs",
  "applications",
  "application",
  "preferences",
  "templates",
  "sources",
  "settings",
]);

/**
 * A screen whose code or first render fails says so and offers a reload; a
 * new dashboard version replaces the files an open tab still points to.
 */
class Boundary extends Component<
  { name: string; children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(error: unknown) {
    console.error(error);
  }
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div role="alert" className="shell-failed">
        <EmptyState
          icon={RotateCw}
          title={`${this.props.name} could not be loaded`}
          actions={
            <Button variant="primary" onClick={() => location.reload()}>
              Reload the dashboard
            </Button>
          }
        >
          The dashboard may have been updated, or the connection was
          interrupted.
        </EmptyState>
      </div>
    );
  }
}

/** The routed screen: loading skeleton, failure with a reload, its frame. */
export function Screen({ id }: { id: RouteId }) {
  const View = SCREENS[id];
  const name = ROUTES[id].title;
  const body = <View />;
  return (
    <Boundary key={id} name={name}>
      <Suspense
        fallback={
          <div className="shell-loading">
            <SkeletonRows rows={6} />
          </div>
        }
      >
        {LEGACY.has(id) ? (
          <div className="legacy-screen" data-screen={id}>
            {body}
          </div>
        ) : (
          <div className="shell-screen" data-screen={id}>
            {body}
          </div>
        )}
      </Suspense>
    </Boundary>
  );
}
