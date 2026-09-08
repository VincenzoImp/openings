import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

import { Button } from "../components/Button";

interface Props {
  children: ReactNode;
  /** Resets the boundary when it changes (e.g. the route). */
  resetKey?: string;
}

interface State {
  error: Error | null;
}

/** Catches render errors so one broken view never blanks the whole page. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Openings view crashed", error, info.componentStack);
  }

  componentDidUpdate(previous: Props): void {
    if (previous.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render(): ReactNode {
    if (!this.state.error) {
      return this.props.children;
    }
    return (
      <div role="alert" className="m-4 rounded-lg border border-negative/40 bg-surface p-4 text-sm">
        <p className="font-semibold text-negative">Something went wrong in this view.</p>
        <p className="mt-1 break-words font-mono text-xs text-fg-muted">
          {this.state.error.message}
        </p>
        <div className="mt-3 flex gap-2">
          <Button variant="primary" onClick={() => this.setState({ error: null })}>
            Try Again
          </Button>
          <Button onClick={() => window.location.reload()}>Reload Page</Button>
        </div>
      </div>
    );
  }
}
