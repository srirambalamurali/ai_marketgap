import { Suspense } from "react";
import { Skeleton } from "@/components/ui";
import SignalsClient from "./signals-client";

export default function SignalsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-[60vh]" />}>
      <SignalsClient />
    </Suspense>
  );
}
