"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TriangleAlert } from "lucide-react";
import * as api from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, SecondaryButton, TextField } from "@/components/ui";

export default function AccountPage() {
  usePageTitle("Account — ReflectInterview");
  const { user, token, logout } = useAuth();
  const router = useRouter();

  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  async function handleDelete() {
    if (!token) return;
    setError(null);
    if (!password) {
      setError("Enter your password to confirm.");
      return;
    }
    setLoading(true);
    try {
      const result = await api.deleteAccount(password, token);
      setDone(result.message);
      // The account is gone, so the token in localStorage now points at
      // nothing. Clear it before navigating or the next page load spends a
      // request discovering the user 404s.
      logout();
      setTimeout(() => router.push("/"), 2500);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <h1 className="ri-display text-3xl">Account</h1>
        <Alert kind="info">
          <Link href="/login" className="font-semibold underline">
            Log in
          </Link>{" "}
          to manage your account. You can also{" "}
          <Link href="/delete-account" className="font-semibold underline">
            read how account deletion works
          </Link>{" "}
          without logging in.
        </Alert>
      </div>
    );
  }

  return (
    <div className="ri-enter mx-auto max-w-lg space-y-6">
      <div>
        <h1 className="ri-display text-3xl">Account</h1>
        <p className="ri-prose mt-2 text-sm text-ri-text-mute">
          Signed in as <b className="text-ri-text">{user.email}</b>
          {user.name ? ` (${user.name})` : ""}.
        </p>
      </div>

      <Card>
        <h2 className="ri-title text-base">What we store</h2>
        <ul className="mt-3 space-y-1.5 text-sm text-ri-text-mute">
          <li>Your email address and name, and a hash of your password.</li>
          <li>
            Résumés, interview answers and generated reports — but only from sessions where you
            ticked the save option. Sessions you did not opt in to save are never written down.
          </li>
        </ul>
        <p className="mt-3 text-sm text-ri-text-mute">
          See <Link href="/delete-account" className="text-ri-accent hover:underline">account deletion</Link>{" "}
          for what removal covers.
        </p>
      </Card>

      <Card className="border-ri-stress/30">
        <h2 className="ri-title flex items-center gap-2 text-base" style={{ color: "var(--ri-stress)" }}>
          <TriangleAlert size={16} strokeWidth={2} aria-hidden />
          Delete account
        </h2>
        <p className="mt-2 text-sm text-ri-text-mute">
          This permanently removes your account and every résumé, answer and report stored against
          it. It cannot be undone and there is no backup to restore from.
        </p>

        {done ? (
          <div className="mt-4">
            <Alert kind="success">{done} Returning to the home page…</Alert>
          </div>
        ) : !confirming ? (
          <div className="mt-4">
            <SecondaryButton onClick={() => setConfirming(true)} className="!text-ri-stress">
              Delete my account
            </SecondaryButton>
          </div>
        ) : (
          <div className="mt-4 space-y-3">
            {error && <Alert kind="error">{error}</Alert>}
            <TextField
              label="Confirm your password"
              type="password"
              value={password}
              onChange={setPassword}
              help="Required because this cannot be reversed."
            />
            <div className="flex flex-wrap gap-2">
              <PrimaryButton onClick={handleDelete} disabled={loading}>
                {loading ? "Deleting…" : "Permanently delete"}
              </PrimaryButton>
              <SecondaryButton
                onClick={() => {
                  setConfirming(false);
                  setPassword("");
                  setError(null);
                }}
                disabled={loading}
              >
                Cancel
              </SecondaryButton>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
