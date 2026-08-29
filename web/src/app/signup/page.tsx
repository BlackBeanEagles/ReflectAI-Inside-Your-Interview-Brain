"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { friendlyError, usePageTitle } from "@/lib/hooks";
import { Alert, Card, PrimaryButton, TextField } from "@/components/ui";

export default function SignupPage() {
  usePageTitle("Sign up — ReflectInterview");
  const { signup } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email || !password) {
      setError("Enter an email and password.");
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
      await signup(email.trim(), password, name.trim() || undefined);
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
        <h1 className="text-xl font-bold mb-1">Sign up</h1>
        <p className="text-sm text-ri-text-mute mb-5">
          Optional — everything works fine without an account too.
        </p>
        {error && (
          <div className="mb-4">
            <Alert kind="error">{error}</Alert>
          </div>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <TextField label="Email" value={email} onChange={setEmail} type="email" />
          <TextField label="Password" value={password} onChange={setPassword} type="password"
            help="At least 8 characters." />
          <TextField label="Confirm password" value={confirm} onChange={setConfirm} type="password" />
          <TextField label="Name (optional)" value={name} onChange={setName} />
          <PrimaryButton type="submit" disabled={loading} className="w-full">
            {loading ? "Creating account…" : "Sign up"}
          </PrimaryButton>
        </form>
        <div className="mt-4 text-sm text-center">
          Already have an account?{" "}
          <Link href="/login" className="text-ri-accent hover:underline">
            Log in
          </Link>
        </div>
      </Card>
    </div>
  );
}
