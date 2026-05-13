import { Button, Card, CardContent } from "@heroui/react";
import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Dashboard render failure", error, info.componentStack);
  }

  render() {
    if (!this.state.error) {
      return this.props.children;
    }

    return (
      <Card className="mx-auto max-w-xl border border-red-200 shadow-sm" variant="default">
        <CardContent className="grid gap-4 p-5">
          <div>
            <h2 className="text-lg font-semibold text-zinc-950">Dashboard view failed</h2>
            <p className="mt-1 text-sm leading-6 text-zinc-600">
              The current view crashed while rendering. Reset the view and reload the dashboard.
            </p>
          </div>
          <Button onPress={() => this.setState({ error: null })} variant="primary">
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }
}
