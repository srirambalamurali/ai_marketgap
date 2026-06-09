"use client";

import { useEffect } from "react";

export default function OpportunityDetailError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Opportunity detail page error:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <div className="max-w-lg rounded-2xl border border-red-500/30 bg-red-500/10 p-6 text-red-100">
        <h2 className="text-xl font-semibold">Unable to render opportunity. Please refresh.</h2>
        <p className="mt-2 text-sm text-red-200/80">A rendering error occurred while loading this page.</p>
        <button type="button" onClick={reset} className="mt-4 rounded-xl bg-red-500 px-4 py-2 text-sm font-medium text-white">
          Retry
        </button>
      </div>
    </div>
  );
}
