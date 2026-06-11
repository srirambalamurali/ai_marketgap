"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Panel, SectionTitle } from "@/components/ui";
import { useAuth } from "@/components/auth-provider";

export default function RegisterPage() {
  const router = useRouter();
  const { register, isAuthenticated, loading } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const goToDashboard = useCallback(() => {
    if (typeof window !== "undefined") {
      window.location.assign("/dashboard");
      return;
    }
    router.replace("/dashboard");
  }, [router]);

  useEffect(() => {
    if (!loading && isAuthenticated) {
      goToDashboard();
    }
  }, [loading, isAuthenticated, goToDashboard]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      await register({ name, email, password });
      toast.success("Account created");
      goToDashboard();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Registration failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto flex min-h-[70vh] max-w-xl items-center">
      <Panel className="w-full space-y-6">
        <SectionTitle title="Register" subtitle="Create your AI Market Gap Intelligence account" />
        <form className="space-y-4" onSubmit={onSubmit}>
          <label className="block space-y-2">
            <span className="text-sm text-slate-300">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
              placeholder="Sriram"
              required
            />
          </label>
          <label className="block space-y-2">
            <span className="text-sm text-slate-300">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
              placeholder="test@example.com"
              required
            />
          </label>
          <label className="block space-y-2">
            <span className="text-sm text-slate-300">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
              placeholder="At least 6 characters"
              required
            />
          </label>
          <label className="block space-y-2">
            <span className="text-sm text-slate-300">Confirm Password</span>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full rounded-xl border border-white/10 bg-black/20 px-4 py-3 outline-none"
              placeholder="Repeat password"
              required
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-xl bg-accent px-4 py-3 font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Creating account..." : "Register"}
          </button>
        </form>
        <div className="text-sm text-slate-400">
          Already have an account? <Link href="/login" className="text-cyan-300 underline">Login</Link>
        </div>
      </Panel>
    </div>
  );
}
