import { Bot, User } from "lucide-react";

interface Props {
  role: "user" | "assistant";
  content: string;
}

export default function ChatMessage({ role, content }: Props) {
  const isUser = role === "user";
  return (
    <div className={`flex animate-fade-slide-in items-start gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}>
      <div
        className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${
          isUser ? "bg-ink-700 text-ink-200" : "bg-violet-ai-dim text-violet-ai"
        }`}
      >
        {isUser ? <User size={14} /> : <Bot size={14} />}
      </div>
      <div
        className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13.5px] leading-relaxed ${
          isUser ? "bg-ink-700 text-ink-100" : "bg-ink-800 text-ink-200"
        }`}
      >
        {content}
      </div>
    </div>
  );
}
