"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { resetPassword } from "@/lib/api";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextField } from "@/components/ui";

function ResetPasswordForm() {
  usePageTitle("Reset password — ReflectInterview");
  const params = useSearchParams();
  // The backend's email link currently points to /?reset_token=... (a
  // convention from when the Streamlit app -- which has no real routing --
  // was the only frontend). Accepting both param names here means this
  // page works with existing emailed links without requiring a backend
  // change that could affect the Streamlit app while it's still live.
  const token = params.get("token") || params.get("reset_token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (!token) {
      setError("This reset link is missing its token.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setLoading(true);
    try {
      const result = await resetPassword(token, password);
      setMessage(result.message);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center">
      <div className="max-w-sm w-full ri-fade-in">
        <Card>
          <h1 className="text-xl font-bold mb-1">🔑 Set a new password</h1>
          <p className="text-sm text-ri-text-mute mb-5">
            This link is single-use and expires 1 hour after it was requested.
          </p>
          {!token && (
            <div className="mb-4">
              <Alert kind="error">No reset token found in this link.</Alert>
            </div>
          )}
          {error && (
            <div className="mb-4">
              <Alert kind="error">{error}</Alert>
            </div>
          )}
          {message ? (
            <>
              <Alert kind="success">{message}</Alert>
              <div className="mt-4 text-sm text-center">
                <Link href="/login" className="text-ri-accent hover:underline">
                  Go to log in
                </Link>
              </div>
            </>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <TextField label="New password" value={password} onChange={setPassword} type="password" />
              <TextField label="Confirm new password" value={confirm} onChange={setConfirm} type="password" />
              <PrimaryButton type="submit" disabled={loading || !token} className="w-full">
                {loading ? "Updating…" : "Update password"}
              </PrimaryButton>
            </form>
          )}
        </Card>
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
