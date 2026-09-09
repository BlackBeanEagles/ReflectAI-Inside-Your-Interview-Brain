"use client";

// Google Play requires apps that let users create an account to publish a
// URL, reachable WITHOUT logging in, that explains how to request deletion
// and what it removes. That is what this page is -- it is linked from the
// Play listing, so it must stay publicly accessible and must not redirect
// to a login wall.

import Link from "next/link";
import { usePageTitle } from "@/lib/hooks";
import { Card } from "@/components/ui";

export default function DeleteAccountInfoPage() {
  usePageTitle("Deleting your account — ReflectInterview");

  return (
    <div className="ri-enter mx-auto max-w-2xl space-y-6">
      <div>
        <p className="ri-eyebrow">ReflectInterview</p>
        <h1 className="ri-display mt-2 text-3xl">Deleting your account</h1>
        <p className="ri-prose mt-3 text-ri-text-mute">
          You can delete your ReflectInterview account and its data yourself, at any time, without
          contacting anyone.
        </p>
      </div>

      <Card>
        <h2 className="ri-title text-base">How to delete it</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-ri-text-mute">
          <li>
            <Link href="/login" className="text-ri-accent hover:underline">
              Log in
            </Link>{" "}
            to the account you want removed.
          </li>
          <li>
            Open{" "}
            <Link href="/account" className="text-ri-accent hover:underline">
              Account
            </Link>
            .
          </li>
          <li>Choose <b className="text-ri-text">Delete my account</b> and confirm with your password.</li>
        </ol>
        <p className="mt-3 text-sm text-ri-text-mute">
          Deletion happens immediately. It cannot be undone and there is no backup to restore from.
        </p>
      </Card>

      <Card>
        <h2 className="ri-title text-base">What is deleted</h2>
        <ul className="mt-3 space-y-1.5 text-sm text-ri-text-mute">
          <li>Your account: email address, name and password hash.</li>
          <li>Every résumé you saved, including its parsed skills, projects and experience.</li>
          <li>Every interview answer stored against your account, and its scores and feedback.</li>
          <li>Every generated session report.</li>
          <li>Any outstanding password-reset links, which stop working immediately.</li>
        </ul>
        <p className="mt-3 text-sm text-ri-text-mute">
          All of it is removed outright rather than merely unlinked from your account.
        </p>
      </Card>

      <Card>
        <h2 className="ri-title text-base">What was never stored</h2>
        <p className="mt-2 text-sm leading-relaxed text-ri-text-mute">
          Interviews you ran without ticking the save option are not written to the database at all
          — they live in server memory for the length of the session and are discarded when it
          ends, so there is nothing of theirs to delete. Voice recordings are transcribed and never
          retained.
        </p>
      </Card>

      <p className="text-xs text-ri-text-mute">
        Using the app without an account remains possible; an account only exists so your history
        can follow you between visits.
      </p>
    </div>
  );
}
