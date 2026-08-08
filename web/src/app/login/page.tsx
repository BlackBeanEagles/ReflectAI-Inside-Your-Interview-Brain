"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextField } from "@/components/ui";

export default function LoginPage() {
  usePageTitle("Log in — ReflectInterview");
  const { login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email || !password) {
      setError("Enter an email and password.");
      return;
    }
    setLoading(true);
    try {
      await login(email.trim(), password);
      router.push("/");
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-sm mx-auto mt-8">
      <Card>
        <h1 className="text-xl font-bold mb-1">Log in</h1>
        <p className="text-sm text-ri-text-mute mb-5">
          Optional — accounts let your interview history follow you across visits.
        </p>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <TextField label="Email" value={email} onChange={setEmail} type="email" />
          <TextField label="Password" value={password} onChange={setPassword} type="password" />
          <PrimaryButton type="submit" disabled={loading} className="w-full">
            {loading ? "Logging in…" : "Log in"}
          </PrimaryButton>
        </form>
        <div className="flex justify-between mt-4 text-sm">
          <Link href="/forgot-password" className="text-ri-accent hover:underline">
            Forgot password?
          </Link>
          <Link href="/signup" className="text-ri-accent hover:underline">
            Create an account
          </Link>
        </div>
      </Card>
    </div>
  );
}
