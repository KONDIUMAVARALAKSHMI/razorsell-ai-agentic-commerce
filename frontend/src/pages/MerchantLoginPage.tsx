import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock } from "lucide-react";
import { api, ApiError } from "../lib/api";

const TOKEN_KEY = "razorsell_merchant_token";

export function getMerchantToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export default function MerchantLoginPage() {
  const [username, setUsername] = useState("merchant");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.merchantLogin(username, password);
      sessionStorage.setItem(TOKEN_KEY, res.token);
      navigate("/merchant/overview");
    } catch (e) {
      setError(e instanceof ApiError ? "Invalid username or password." : "Could not sign in.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-56px)] items-center justify-center p-4">
      <form onSubmit={handleSubmit} className="w-full max-w-sm rounded-2xl border border-ink-700 bg-ink-900 p-6">
        <div className="mb-5 flex flex-col items-center gap-2 text-center">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-signal-dim text-amber-signal">
            <Lock size={18} />
          </div>
          <p className="font-display text-lg font-semibold">Merchant sign in</p>
          <p className="text-xs text-ink-400">Demo credentials: merchant / demo-password</p>
        </div>

        <label className="mb-1 block text-xs font-medium text-ink-300">Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          className="mb-3 w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-ink-100 focus:border-amber-signal"
        />
        <label className="mb-1 block text-xs font-medium text-ink-300">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mb-4 w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm text-ink-100 focus:border-amber-signal"
        />

        {error && <p className="mb-3 text-xs text-rose-failure">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-lg bg-amber-signal py-2.5 text-sm font-semibold text-ink-950 hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}
