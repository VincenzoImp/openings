import { useState, type FormEvent } from "react";
import { LogOut } from "lucide-react";
import { useShell } from "../../shell/context";
import { useTheme } from "../../shell/theme";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { Field, Input, Select } from "../../ui/Field";
import type { ThemeMode } from "../../ui/theme";
import { useToast } from "../../ui/Toast";
import { useChangePassword, useIsOwner } from "./queries";
import { OwnerOnly, SettingRow, SettingsSection } from "./Rows";

/** Password, theme, the setup guide and signing out. */
export function Account() {
  const { signOut } = useShell();
  const [theme, setTheme] = useTheme();
  const owner = useIsOwner();
  const [password, setPassword] = useState(false);
  return (
    <SettingsSection title="Account">
      {owner && (
        <SettingRow
          title="Password"
          note={<OwnerOnly />}
          control={
            <Button onClick={() => setPassword(true)}>Change password</Button>
          }
        >
          Every browser signs in again; API tokens keep working.
        </SettingRow>
      )}
      <SettingRow
        title="Theme"
        control={
          <Select
            aria-label="Theme"
            className="set-select"
            value={theme}
            onChange={(event) => setTheme(event.target.value as ThemeMode)}
          >
            <option value="system">Same as the system</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </Select>
        }
      >
        Remembered in this browser.
      </SettingRow>
      <SettingRow
        title="Setup guide"
        control={
          <a className="ui-btn" data-variant="secondary" href="#setup">
            <span className="ui-btn-label">Open setup guide</span>
          </a>
        }
      >
        The first steps of a workspace: you, your first search, your CV.
      </SettingRow>
      <SettingRow
        title="Sign out"
        control={
          <Button variant="ghost" icon={LogOut} onClick={signOut}>
            Sign out
          </Button>
        }
      >
        Ends the session of every browser.
      </SettingRow>
      <PasswordDialog open={password} onClose={() => setPassword(false)} />
    </SettingsSection>
  );
}

/** A new owner password, typed twice; then every browser signs in again. */
function PasswordDialog({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const change = useChangePassword();
  const toast = useToast();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const short = password.length < 10;
  const differs = confirm !== password;
  const close = () => {
    setPassword("");
    setConfirm("");
    setSubmitted(false);
    onClose();
  };
  function save(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (short || differs) return;
    change.mutate(password, {
      onSuccess: () => {
        close();
        toast.show({
          message: "Password changed. Sign in with the new one.",
          tone: "success",
        });
        window.dispatchEvent(new Event("openings:unauthorized"));
      },
      onError: (error) => toast.show({ message: error.message, tone: "error" }),
    });
  }
  return (
    <Dialog
      open={open}
      onClose={close}
      title="Change password"
      description="Every browser signs in again with the new password. API tokens keep working."
      initialFocus="input"
      footer={
        <>
          <Button variant="ghost" onClick={close}>
            Cancel
          </Button>
          <Button
            variant="primary"
            type="submit"
            form="password-form"
            disabled={change.isPending}
          >
            Change password
          </Button>
        </>
      }
    >
      <form id="password-form" className="set-form" noValidate onSubmit={save}>
        <Field
          label="New password"
          hint="At least 10 characters."
          error={submitted && short ? "Use at least 10 characters." : undefined}
        >
          <Input
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <Field
          label="Confirm the new password"
          error={
            submitted && !short && differs
              ? "The two passwords are not the same."
              : undefined
          }
        >
          <Input
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
          />
        </Field>
      </form>
    </Dialog>
  );
}
