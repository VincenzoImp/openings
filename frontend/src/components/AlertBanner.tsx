import { Alert } from "@heroui/react";

interface AlertBannerProps {
  children: string;
  kind?: "danger" | "success" | "warning" | "default";
  title?: string;
}

export function AlertBanner({ children, kind = "default", title }: AlertBannerProps) {
  return (
    <Alert
      status={
        kind === "danger"
          ? "danger"
          : kind === "success"
            ? "success"
            : kind === "warning"
              ? "warning"
              : "default"
      }
    >
      <Alert.Content>
        {title ? <Alert.Title>{title}</Alert.Title> : null}
        <Alert.Description>{children}</Alert.Description>
      </Alert.Content>
    </Alert>
  );
}
