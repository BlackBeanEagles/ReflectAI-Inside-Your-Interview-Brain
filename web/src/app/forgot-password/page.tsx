"use client";

import { useState } from "react";
import Link from "next/link";
import { forgotPassword } from "@/lib/api";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextField } from "@/components/ui";

export default function ForgotPasswordPage() {
  usePageTitle("Forgot password — ReflectInterview");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if (!email.trim()) {
      setError("Enter your account email.");
      return;
    }
    setLoading(true);
    try {
      const result = await forgotPassword(email.trim());
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
          <h1 className="text-xl font-bold mb-1">Forgot password?</h1>
          <p className="text-sm text-ri-text-mute mb-5">
            If an account exists for that email, a reset link is sent to it.
          </p>
          {error && (
            <div className="mb-4">
              <Alert kind="error">{error}</Alert>
            </div>
          )}
          {message && (
            <div className="mb-4">
              <Alert kind="success">{message}</Alert>
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <TextField label="Email" value={email} onChange={setEmail} type="email" />
            <PrimaryButton type="submit" disabled={loading} className="w-full">
              {loading ? "Sending…" : "Send reset link"}
            </PrimaryButton>
          </form>
          <div className="mt-4 text-sm text-center">
            <Link href="/login" className="text-ri-accent hover:underline">
              Back to log in
            </Link>
          </div>
        </Card>
      </div>
    </div>
  );
}
