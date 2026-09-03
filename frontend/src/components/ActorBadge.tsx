interface ActorBadgeProps {
  actor: string;
}

const ACTOR_STYLES: Record<string, string> = {
  USER: "text-ink-100 border-ink-500",
  AI: "text-violet-ai border-violet-ai/40",
  SYSTEM: "text-ink-300 border-ink-600",
  RAZORPAY: "text-amber-signal border-amber-signal/40",
};

export default function ActorBadge({ actor }: ActorBadgeProps) {
  const style = ACTOR_STYLES[actor] || "text-ink-300 border-ink-600";
  return (
    <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${style}`}>
      {actor}
    </span>
  );
}
