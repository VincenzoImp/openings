import { Component, Suspense, lazy, type ReactNode } from "react";
import { Button, ErrorBanner, Loading } from "../design";
import { SCREENS } from "./routes";

// Each screen is its own chunk, loaded when it is first opened (or when the
// pointer or focus reaches its navigation link). The first screen's JavaScript
// stays within the budget checked by scripts/budget.mjs.
const loaders = {
  today: () => import("../pages/Today"),
  activity: () => import("../pages/Activity"),
  jobs: () => import("../pages/Jobs"),
  applications: () => import("../pages/Applications"),
  review: () => import("../pages/Review"),
  collection: () => import("../pages/Collection"),
  career: () => import("../pages/Career"),
  policy: () => import("../pages/Policy"),
  templates: () => import("../pages/Templates"),
  settings: () => import("../pages/Settings"),
};
const chunkOf: Record<string, keyof typeof loaders> = {
  inbox: "jobs",
  shortlist: "jobs",
};

/** Start loading a screen's code before it is opened. */
export function preloadScreen(route: string) {
  const name = chunkOf[route] ?? route;
  if (name in loaders)
    void loaders[name as keyof typeof loaders]().catch(() => {
      // The screen reports the failure itself when it is opened.
    });
}

export const TodayPage = lazy(loaders.today);
export const ActivityPage = lazy(loaders.activity);
export const CollectionPage = lazy(loaders.collection);
export const CareerPage = lazy(loaders.career);
export const PolicyPage = lazy(loaders.policy);
export const TemplatesPage = lazy(loaders.templates);
export const SettingsPage = lazy(loaders.settings);
export const JobsPage = lazy(() =>
  loaders.jobs().then((module) => ({ default: module.JobsPage })),
);
export const JobDrawer = lazy(() =>
  loaders.jobs().then((module) => ({ default: module.JobDrawer })),
);
export const AddJob = lazy(() =>
  loaders.jobs().then((module) => ({ default: module.AddJob })),
);
export const ApplicationsPage = lazy(loaders.applications);
export const ReviewPage = lazy(loaders.review);

interface BoundaryProps {
  /** What failed, for the message: "Applications" or "this job". */
  name: string;
  children: ReactNode;
}
/**
 * A screen whose code or first render fails says so and offers a reload; a
 * new dashboard version replaces the files an open tab still points to.
 */
class ScreenBoundary extends Component<BoundaryProps, { failed: boolean }> {
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
      <div className="stack">
        <h1>{this.props.name}</h1>
        <ErrorBanner
          message={`${this.props.name} could not be loaded. The dashboard may have been updated, or the connection was interrupted.`}
        />
        <Button variant="primary" onClick={() => location.reload()}>
          Reload the dashboard
        </Button>
      </div>
    );
  }
}

/** The frame of a routed screen: loading state and failure with a reload. */
export function Screen({
  route,
  children,
}: {
  route: string;
  children: ReactNode;
}) {
  const name = SCREENS[route] || "This screen";
  return (
    <ScreenBoundary key={route} name={name}>
      <Suspense fallback={<Loading label={`Loading ${name}…`} />}>
        {children}
      </Suspense>
    </ScreenBoundary>
  );
}

/** The frame of an object opened over a screen (a job or an application). */
export function Overlay({
  name,
  children,
}: {
  name: string;
  children: ReactNode;
}) {
  return (
    <OverlayBoundary name={name}>
      <Suspense fallback={null}>{children}</Suspense>
    </OverlayBoundary>
  );
}
class OverlayBoundary extends ScreenBoundary {
  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="toast error" role="alert">
        <span className="grow">{this.props.name} could not be loaded. </span>
        <Button size="sm" onClick={() => location.reload()}>
          Reload
        </Button>
      </div>
    );
  }
}
