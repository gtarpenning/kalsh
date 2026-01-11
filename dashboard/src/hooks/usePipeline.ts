import { useState } from "react";

export function usePipeline(onSuccess: () => Promise<void>) {
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState("");

  const triggerPipeline = async () => {
    setIsStarting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const res = await fetch(`${apiUrl}/api/pipelines`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        throw new Error("pipeline request failed");
      }
      await onSuccess();
    } catch (err) {
      console.error(err);
      setError("Pipeline service is unreachable. Try again in a second.");
    } finally {
      setIsStarting(false);
    }
  };

  return { isStarting, error, triggerPipeline };
}
